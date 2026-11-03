"""One bounded request per call, on an explicitly supplied session only.

No session, connection or network activity is created at import/construction.
One instance is shared across sequential targets to enforce global spacing.
The controller owns budgets, fallback, durable request intent and live gating.
"""
from dataclasses import dataclass, field, replace
import math
import re
import threading
import time

from requests.adapters import HTTPAdapter
from requests.exceptions import Timeout

from .contracts import FeedFormat, IngestionConfig

# Pinned sampling-frame IDs from results/mainstream/app_sample_manifest.json.
PILOT_APPLICATION_IDS = frozenset({"572688855", "1212616790", "570060128", "469863705",
                                   "297606951", "477128284", "368677368", "529379082"})


@dataclass(frozen=True)
class FetchResponse:
    status_code: int | None
    body: bytes = field(repr=False)
    response_bytes: int
    error_code: str | None = None


class BoundedTransport:
    def __init__(self, session, *, clock=time.monotonic, sleep=time.sleep):
        if session is None or not callable(getattr(session, "get", None)):
            raise ValueError("EXPLICIT_SESSION_REQUIRED")
        self._session = session
        self._clock, self._sleep = clock, sleep
        self._last_request_at = None
        self._mutex = threading.Lock()

    def _scrub_session(self, selected):
        session = self._session
        session.trust_env = False
        session.auth = None
        session.cert = None
        session.proxies = {}
        session.params = {}
        session.headers = {
            "User-Agent": "DataSourceFeasibility/0.1 (bounded Apple ingestion pilot)",
            "Accept": "application/json" if selected is FeedFormat.JSON else "application/atom+xml, application/xml",
        }
        session.hooks = {"response": []}
        session.verify = True
        cookies = getattr(session, "cookies", None)
        if cookies is not None:
            cookies.clear()
        # Disable adapter retries on injected requests.Session instances too.
        for adapter in getattr(session, "adapters", {}).values():
            adapter.max_retries = HTTPAdapter(max_retries=0).max_retries

    def fetch(self, source_application_id, page, format, config, *, deadline=None) -> FetchResponse:
        """Return only a successful 200 body; all failures discard partial text.

        deadline is an absolute value on the injected monotonic clock. A read
        timeout is not a total-response deadline; streaming also checks it.
        Injected fake sessions must implement exactly one request per get call.
        """
        try:
            if (type(source_application_id) is not str
                    or not re.fullmatch(r"[0-9]{1,20}", source_application_id)
                    or source_application_id not in PILOT_APPLICATION_IDS
                    or type(page) is not int or type(config) is not IngestionConfig):
                return FetchResponse(None, b"", 0, "INVALID_REQUEST")
            config = replace(config)  # Revalidate callers that bypass frozen fields.
            selected = FeedFormat(format)
            if not 1 <= page <= config.max_pages:
                return FetchResponse(None, b"", 0, "INVALID_REQUEST")
            if deadline is not None and (type(deadline) not in (int, float) or not math.isfinite(deadline)):
                return FetchResponse(None, b"", 0, "INVALID_REQUEST")
        except Exception:
            return FetchResponse(None, b"", 0, "INVALID_REQUEST")
        url = (f"https://itunes.apple.com/us/rss/customerreviews/page={page}/"
               f"id={source_application_id}/sortby=mostrecent/{selected.value}")
        status, received = None, 0

        def expired():
            return deadline is not None and self._clock() >= deadline

        with self._mutex:
            try:
                if expired():
                    return FetchResponse(None, b"", 0, "TARGET_DEADLINE")
                if self._last_request_at is not None:
                    delay = max(0, self._last_request_at + config.global_spacing_seconds - self._clock())
                    if deadline is not None and self._clock() + delay >= deadline:
                        return FetchResponse(None, b"", 0, "TARGET_DEADLINE")
                    if delay:
                        self._sleep(delay)
                    # A fake clock/sleeper must not allow a burst by undersleeping.
                    if self._clock() < self._last_request_at + config.global_spacing_seconds:
                        return FetchResponse(None, b"", 0, "TRANSPORT_CLOCK")
                if expired():
                    return FetchResponse(None, b"", 0, "TARGET_DEADLINE")
                self._scrub_session(selected)
                self._last_request_at = self._clock()
                with self._session.get(url, allow_redirects=False, stream=True,
                                       timeout=(config.connect_timeout_seconds, config.read_timeout_seconds)) as response:
                    status = response.status_code
                    if type(status) is not int or not 100 <= status <= 599:
                        return FetchResponse(None, b"", 0, "HTTP_NON_200")
                    if status != 200:
                        code = "HTTP_DENIED" if status in (401, 403) else "HTTP_RATE_LIMIT" if status == 429 else "HTTP_NON_200"
                        return FetchResponse(status, b"", 0, code)
                    content = bytearray()
                    for chunk in response.iter_content(chunk_size=16_384):
                        if expired():
                            return FetchResponse(status, b"", received, "TARGET_DEADLINE")
                        if type(chunk) is not bytes:
                            return FetchResponse(status, b"", received, "TRANSPORT_ERROR")
                        received += len(chunk)
                        if received > config.max_response_bytes:
                            return FetchResponse(status, b"", received, "BODY_LIMIT")
                        content.extend(chunk)
                    if expired():
                        return FetchResponse(status, b"", received, "TARGET_DEADLINE")
                    return FetchResponse(status, bytes(content), received)
            except (Timeout, TimeoutError):
                return FetchResponse(status, b"", received, "TRANSPORT_TIMEOUT")
            except Exception:
                return FetchResponse(status, b"", received, "TRANSPORT_ERROR")
            finally:
                # Responses may set cookies even if the caller supplied none.
                cookies = getattr(self._session, "cookies", None)
                if cookies is not None:
                    try:
                        cookies.clear()
                    except Exception:
                        pass  # Next request's scrub must succeed before get().
