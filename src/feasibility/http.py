"""Bounded, no-retry transport. Never persist response bodies or credentials."""
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class StopCollection(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class Client:
    def __init__(self, host, max_requests=10, delay=1.0, session=None):
        self.host, self.max_requests, self.delay = host, max_requests, delay
        self.session = session or requests.Session()
        # Avoid ambient netrc authentication. Explicit headers only, no token loading.
        self.session.trust_env = False
        self.session.headers.update({
            "User-Agent": "Agent/Codex DataSourceFeasibility/0.1 (bounded research; no training)",
            "Accept": "application/json",
        })
        self.events, self.blocked = [], False
        self.last_at = None

    def get(self, url, params=None, headers=None):
        if self.blocked:
            raise StopCollection("source_stopped")
        if len(self.events) >= self.max_requests:
            raise StopCollection("request_budget_exhausted")
        u = urlparse(url)
        if u.scheme != "https" or u.hostname != self.host or u.username or u.password:
            raise StopCollection("disallowed_url")
        if self.last_at is not None:
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_at)))
        safe_params = dict(params or {})
        if "input_json" in safe_params:
            import json, hashlib
            safe = json.loads(safe_params['input_json'])
            if safe.get('cursor') != '*' and 'cursor' in safe:
                safe['cursor'] = 'sha256:' + hashlib.sha256(str(safe['cursor']).encode()).hexdigest()
            safe_params['input_json'] = safe
        event = {"at_utc": utcnow(), "url": url, "params": safe_params, "status": None,
                 "error": None, "headers": {}}
        self.events.append(event)
        self.last_at = time.monotonic()
        try:
            # Stream and cap decoded body; no redirects, cookies, retries or auth.
            self.session.cookies.clear()
            with self.session.get(url, params=params, headers=headers, timeout=(10, 25),
                                  allow_redirects=False, stream=True) as resp:
                event["status"] = resp.status_code
                event["headers"] = {k.lower(): v for k, v in resp.headers.items() if k.lower() in {
                    "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset",
                    "retry-after", "etag", "last-modified", "age", "content-type"}}
                if resp.status_code != 200:
                    self.blocked = resp.status_code in (401, 403, 429)
                    raise StopCollection("access_or_rate_denial" if self.blocked else "http_error")
                body = bytearray()
                for chunk in resp.iter_content(16384):
                    body.extend(chunk)
                    if len(body) > 2_000_000:
                        raise StopCollection("response_size_limit")
                import json
                try:
                    data = json.loads(body)
                except (ValueError, UnicodeDecodeError):
                    raise StopCollection("malformed_json")
                if event["headers"].get("x-ratelimit-remaining") == "0":
                    self.blocked = True  # Keep this valid response, then stop before the next request.
                return data
        except requests.RequestException:
            event["error"] = "transport_error"  # No exit IP or proxy details in saved errors.
            raise StopCollection("transport_error")
        except StopCollection as exc:
            event["error"] = exc.code
            raise
        finally:
            event["duration_ms"] = round((time.monotonic() - self.last_at) * 1000)
