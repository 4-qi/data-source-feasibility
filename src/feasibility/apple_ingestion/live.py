"""Default-closed project execution with legacy single-use compatibility.

ProjectExecutionPolicy is the reusable workflow. It validates explicit project
scope/window/settings and needs no approval document or receipt. Execution is
disabled by default. Deployment checks operational DB/diagnostics readiness;
access/retention administrative metadata does not authorize or gate collection.

Only the legacy LiveExecutionApproval/prepare_live_controller path requires an
independent single-run record and private receipt. Its receipt uniqueness is
local to one configured directory. Both paths reuse Controller. This module
performs no import-time I/O and creates no scheduler or automatic pilot.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
import time
from uuid import UUID

import requests

from .contracts import ConfigSnapshot, IngestionConfig, RunMode
from .controller import Controller, ControllerError
from .transport import BoundedTransport, FetchResponse, PILOT_APPLICATION_IDS

APPROVAL_SCHEMA_VERSION = "apple-live-single-run-approval/1"
_REPOSITORY = Path(__file__).resolve().parents[3]


class LivePolicyError(ControllerError):
    pass


def _aware(value):
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LivePolicyError("LIVE_APPROVAL_INVALID")
    return value.astimezone(timezone.utc)


def _text(value):
    return isinstance(value,str) and bool(value.strip()) and "\x00" not in value


def _stamp(value):
    return _aware(value).isoformat(timespec="microseconds").replace("+00:00","Z") if value is not None else None


@dataclass(frozen=True)
class LiveExecutionApproval:
    approval_id: UUID | None = None
    operator: str | None = field(default=None,repr=False)
    approved_by: str | None = field(default=None,repr=False)
    approved_at: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    source_application_ids: tuple[str,...] = ()
    max_http_requests: int = 10
    access_basis_ref: str | None = field(default=None,repr=False)
    retention_policy_ref: str | None = field(default=None,repr=False)
    status: str = "pending"
    readiness_confirmed: bool = False
    execution_authorized: bool = False
    max_runs: int = 1
    storefront: str = "us"
    sort_by: str = "mostrecent"
    schema_version: str = APPROVAL_SCHEMA_VERSION

    def __post_init__(self):
        if (self.schema_version!=APPROVAL_SCHEMA_VERSION or self.status not in {"pending","approved","revoked"}
                or type(self.readiness_confirmed) is not bool or type(self.execution_authorized) is not bool
                or type(self.max_runs) is not int or self.max_runs!=1
                or type(self.max_http_requests) is not int or self.max_http_requests<=0
                or type(self.source_application_ids) is not tuple
                or any(type(value) is not str or value not in PILOT_APPLICATION_IDS for value in self.source_application_ids)
                or len(set(self.source_application_ids))!=len(self.source_application_ids)
                or self.storefront!="us" or self.sort_by!="mostrecent"):
            raise LivePolicyError("LIVE_APPROVAL_INVALID")

    def to_dict(self):
        value=asdict(self)
        value["approval_id"]=str(self.approval_id) if self.approval_id is not None else None
        value["source_application_ids"]=list(self.source_application_ids)
        for name in ("approved_at","valid_from","valid_until"): value[name]=_stamp(value[name])
        return value

    @classmethod
    def from_dict(cls,value):
        try:
            if type(value) is not dict or set(value)!={item.name for item in fields(cls)}:
                raise ValueError
            data=dict(value)
            if data["approval_id"] is not None: data["approval_id"]=UUID(data["approval_id"])
            if type(data["source_application_ids"]) is not list: raise ValueError
            data["source_application_ids"]=tuple(data["source_application_ids"])
            for name in ("approved_at","valid_from","valid_until"):
                if data[name] is not None:
                    data[name]=_aware(datetime.fromisoformat(data[name].replace("Z","+00:00")))
            return cls(**data)
        except Exception:
            raise LivePolicyError("LIVE_APPROVAL_INVALID") from None


def approval_template() -> dict:
    """Unapproved record only; caller must not infer live permission from it."""
    return LiveExecutionApproval().to_dict()


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()


def _deployment_binding(config):
    """Bind operational settings; retention documentation is metadata only."""
    value=config.to_dict()
    value.pop("retention",None)
    return _digest(value)


class LiveExecutionPolicy:
    """One explicit approval, one private receipt, one Controller.run_target.

    receipt_directory must already exist, be outside the repository, owned by
    this user and mode 0700 (or stricter). A claim reserves the approval even if
    HTTP Session construction or subsequent lock acquisition fails. Recovery
    needs a new independent approval; receipt deletion is never automatic.
    """
    def __init__(self,approval: LiveExecutionApproval,receipt_directory):
        if type(approval) is not LiveExecutionApproval:
            raise LivePolicyError("LIVE_APPROVAL_INVALID")
        self.approval=approval
        self.receipt_directory=Path(receipt_directory)
        self._binding=None
        self._prepared_binding=None
        self._deployment_config=None
        self._readiness_check=None
        self._begun=False
        self._closed=False
        self._mutex=threading.Lock()

    def validate(self,snapshot: ConfigSnapshot,batch_id: UUID | None,at: datetime,*,runtime_engine=None):
        approval=replace(self.approval)  # Revalidate frozen fields if bypassed.
        now=_aware(at)
        if approval.status!="approved" or not approval.readiness_confirmed or not approval.execution_authorized:
            raise LivePolicyError("LIVE_MODE_DISABLED")
        if (type(approval.approval_id) is not UUID or not approval.source_application_ids
                or not _text(approval.operator)):
            raise LivePolicyError("LIVE_APPROVAL_INVALID")
        approved_at,valid_from,valid_until=map(_aware,(approval.approved_at,approval.valid_from,approval.valid_until))
        if approved_at>now or valid_from>=valid_until or approved_at>=valid_until:
            raise LivePolicyError("LIVE_APPROVAL_INVALID")
        if not valid_from<=now<valid_until:
            raise LivePolicyError("LIVE_APPROVAL_OUTSIDE_VALIDITY")
        if type(snapshot) is not ConfigSnapshot or snapshot.run_mode is not RunMode.LIVE:
            raise LivePolicyError("LIVE_SNAPSHOT_REQUIRED")
        if (snapshot.source_application_id not in approval.source_application_ids
                or snapshot.storefront!=approval.storefront or snapshot.sort_by!=approval.sort_by
                or snapshot.config.max_http_requests>approval.max_http_requests):
            raise LivePolicyError("LIVE_APPROVAL_SCOPE_MISMATCH")
        if batch_id is not None and type(batch_id) is not UUID:
            raise LivePolicyError("LIVE_APPROVAL_SCOPE_MISMATCH")
        if self._closed:
            raise LivePolicyError("LIVE_APPROVAL_CONSUMED")
        binding=self._prepared_binding or self._binding
        if binding is not None and (binding[0]!=_digest(snapshot.to_dict())
                or batch_id is not None and binding[1]!=batch_id):
            raise LivePolicyError("LIVE_APPROVAL_SCOPE_MISMATCH")
        if self._prepared_binding is not None:
            if (runtime_engine is not None and runtime_engine is not self._prepared_binding[2]
                    or _deployment_binding(self._deployment_config)!=self._prepared_binding[3]):
                raise LivePolicyError("LIVE_APPROVAL_SCOPE_MISMATCH")

    def validate_target(self,snapshot,enabled,at):
        self.validate(snapshot,None,at)
        if enabled is not True:
            raise LivePolicyError("LIVE_TARGET_DISABLED")

    @property
    def operator(self):
        return self.approval.operator

    def remaining_seconds(self,at):
        return max(0.0,(_aware(self.approval.valid_until)-_aware(at)).total_seconds())

    def claim(self,snapshot,batch_id,at):
        with self._mutex:
            self.validate(snapshot,batch_id,at)
            if self._binding is not None:
                raise LivePolicyError("LIVE_APPROVAL_CONSUMED")
            directory=self.receipt_directory
            descriptor=None
            output=None
            try:
                if not directory.is_absolute() or directory.resolve()!=directory or directory.is_relative_to(_REPOSITORY):
                    raise LivePolicyError("LIVE_PRIVATE_RECEIPT_DIRECTORY_REQUIRED")
                if any((parent/".git").is_file() or (parent/".git/HEAD").is_file() for parent in (directory,*directory.parents)):
                    raise LivePolicyError("LIVE_PRIVATE_RECEIPT_DIRECTORY_REQUIRED")
                descriptor=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
                metadata=os.fstat(descriptor)
                if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid!=os.getuid() or metadata.st_mode & 0o077:
                    raise LivePolicyError("LIVE_PRIVATE_RECEIPT_DIRECTORY_REQUIRED")
                receipt={"approval_id":str(self.approval.approval_id),"approval_sha256":_digest(self.approval.to_dict()),
                    "snapshot_sha256":_digest(snapshot.to_dict()),"batch_id":str(batch_id),"claimed_at":_stamp(at),"max_runs":1}
                output=os.open(str(self.approval.approval_id)+".json",os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=descriptor)
                payload=(json.dumps(receipt,sort_keys=True,separators=(",",":"))+"\n").encode("utf-8")
                with os.fdopen(output,"wb") as handle:
                    output=None
                    handle.write(payload); handle.flush(); os.fsync(handle.fileno())
                os.fsync(descriptor)
                self._binding=receipt["snapshot_sha256"],batch_id
            except FileExistsError:
                raise LivePolicyError("LIVE_APPROVAL_CONSUMED") from None
            except LivePolicyError:
                raise
            except Exception:
                raise LivePolicyError("LIVE_APPROVAL_RECEIPT_UNAVAILABLE") from None
            finally:
                if output is not None: os.close(output)
                if descriptor is not None: os.close(descriptor)

    def prepare(self,snapshot,batch_id,at,*,runtime_engine,deployment_config,readiness_check):
        with self._mutex:
            self.validate(snapshot,batch_id,at)
            if self._prepared_binding is not None or self._binding is not None:
                raise LivePolicyError("LIVE_APPROVAL_CONSUMED")
            self._deployment_config=deployment_config
            self._prepared_binding=_digest(snapshot.to_dict()),batch_id,runtime_engine,_deployment_binding(deployment_config)
            self._readiness_check=readiness_check

    def begin_execution(self,snapshot,batch_id,at,*,runtime_engine=None):
        self.validate(snapshot,batch_id,at,runtime_engine=runtime_engine)
        if self._prepared_binding is None:
            raise LivePolicyError("LIVE_APPROVAL_NOT_PREPARED")
        if runtime_engine is not self._prepared_binding[2] or not callable(self._readiness_check):
            raise LivePolicyError("LIVE_APPROVAL_SCOPE_MISMATCH")
        self._readiness_check()  # Fresh actual-login deployment/target check.
        # Atomic filesystem reservation also protects separate Policy instances
        # and processes sharing this same, privately managed receipt directory.
        self.claim(snapshot,batch_id,at)
        with self._mutex:
            if self._begun:
                raise LivePolicyError("LIVE_APPROVAL_CONSUMED")
            self._begun=True

    def close(self):
        self._closed=True


class _CheckedSession:
    """Final GET guard after transport spacing, before the actual HTTP call."""
    def __init__(self,session,check):
        object.__setattr__(self,"_session",session)
        object.__setattr__(self,"_check",check)
    def __getattr__(self,name):
        return getattr(self._session,name)
    def __setattr__(self,name,value):
        setattr(self._session,name,value)
    def get(self,url,**kwargs):
        self._check(url)
        return self._session.get(url,**kwargs)


class _PreparedTransport:
    """Lazy HTTP resource only; every fetch delegates to BoundedTransport."""
    def __init__(self,policy,session_factory,clock,sleep,*,before_send=None):
        self.policy,self.factory,self.clock,self.sleep=policy,session_factory,clock,sleep
        self.before_send=before_send
        self.blocked_code=None
        self.session=None
        self.transport=None

    def fetch(self,*args,**kwargs):
        self.blocked_code=None
        if not self.policy._begun or self.policy._closed:
            raise LivePolicyError("LIVE_APPROVAL_NOT_PREPARED")
        if self.transport is None:
            self.session=(self.factory or requests.Session)()
            if not isinstance(self.session,requests.Session):
                raise LivePolicyError("LIVE_SESSION_CREATION_FAILED")
            self.session.trust_env=False
            self.session.auth=None
            self.session.cert=None
            self.session.proxies={}
            self.session.verify=True
            guarded=self.session
            if self.before_send is not None:
                def check(url):
                    try:
                        self.before_send(url)
                    except LivePolicyError as exc:
                        self.blocked_code=exc.code
                        raise
                guarded=_CheckedSession(self.session,check)
            self.transport=BoundedTransport(guarded,clock=self.clock,sleep=self.sleep)
        result=self.transport.fetch(*args,**kwargs)
        return FetchResponse(None,b"",0,self.blocked_code) if self.blocked_code else result

    def close(self):
        if isinstance(self.session,requests.Session): self.session.close()


def _deployment_preflight(engine,audit_engine,config,snapshot,policy,spool,environ):
    from .deployment import DeploymentConfig,preflight
    if type(config) is not DeploymentConfig or audit_engine is None:
        raise LivePolicyError("LIVE_DEPLOYMENT_NOT_READY")
    # Validate operational configuration and the actual diagnostics path.
    # Access/retention references and confirmations are not runtime gates.
    try:
        config=DeploymentConfig.from_dict(config.to_dict())
        environment=os.environ if environ is None else environ
        configured_spool=environment.get(config.diagnostics.spool_path_env)
        if (config.diagnostics.operator!=policy.operator
                or type(configured_spool) is not str or Path(configured_spool)!=spool.path):
            raise LivePolicyError("LIVE_DEPLOYMENT_NOT_READY")
        for candidate in (engine,audit_engine):
            if (candidate.dialect.name!="postgresql" or candidate.dialect.driver!="psycopg"
                    or candidate.echo or not candidate.hide_parameters):
                raise LivePolicyError("LIVE_DATABASE_CONFIGURATION_INVALID")
        with engine.connect() as runtime,audit_engine.connect() as audit:
            with runtime.begin(),audit.begin():
                # Compare the actual connected libpq endpoints/database as
                # well as the catalog OID, not an unauthenticated report dict.
                def identity(connection):
                    from sqlalchemy import text
                    info=connection.connection.driver_connection.info
                    oid=connection.scalar(text("SELECT oid FROM pg_database WHERE datname=current_database()"))
                    return info.host,info.port,info.dbname,oid
                if identity(runtime)!=identity(audit):
                    raise LivePolicyError("LIVE_DEPLOYMENT_DATABASE_MISMATCH")
                result=preflight(audit,config,for_live=True,environ=environment,runtime_connection=runtime)
                if result.get("live_ready") is not True or result.get("runtime_login_verified") is not True:
                    raise LivePolicyError("LIVE_DEPLOYMENT_NOT_READY")
    except LivePolicyError:
        raise
    except Exception:
        raise LivePolicyError("LIVE_DEPLOYMENT_PREFLIGHT_FAILED") from None


@contextmanager
def prepare_live_controller(engine,snapshot,batch_id,spool,*,policy=None,deployment_config=None,
                            audit_engine=None,environ=None,session_factory=None,
                            now=None,clock=time.monotonic,sleep=time.sleep):
    """Read-only preflight, then prepare one run; no automatic HTTP/activation.

    audit_engine is used solely for the deployment SELECT audit and is not
    given to Controller. Collector writes use the verified actual runtime
    login. No extra runtime permission on alembic_version is introduced.
    Session/receipt activation is lazy, so rejected run_batch consumes neither.
    The caller supplies a new independent approval after skips/aborts; this
    function never creates approval, enables targets or schedules a pilot.
    """
    if type(policy) is not LiveExecutionPolicy:
        raise LivePolicyError("LIVE_MODE_DISABLED")
    if type(snapshot) is not ConfigSnapshot or snapshot.run_mode is not RunMode.LIVE:
        raise LivePolicyError("LIVE_SNAPSHOT_REQUIRED")
    controller=Controller(engine,None,spool,now=now,monotonic=clock,live_policy=policy)
    controller._validate(snapshot,batch_id)
    def readiness_check():
        _deployment_preflight(engine,audit_engine,deployment_config,snapshot,policy,spool,environ)
        with engine.connect() as connection:
            with connection.begin(): controller._validate_target(connection,snapshot)
    readiness_check()
    policy.prepare(snapshot,batch_id,controller._time(),runtime_engine=engine,
                   deployment_config=deployment_config,readiness_check=readiness_check)
    transport=_PreparedTransport(policy,session_factory,clock,sleep)
    controller.transport=transport
    try:
        yield controller
    finally:
        policy.close()
        transport.close()


PROJECT_POLICY_SCHEMA_VERSION="apple-project-execution-policy/1"
PROJECT_STOP_CODES=frozenset({"PROJECT_EXECUTION_DISABLED","PROJECT_ACCESS_ARRANGEMENT_PENDING",
    "PROJECT_POLICY_OUTSIDE_VALIDITY","PROJECT_POLICY_CHANGED","PROJECT_POLICY_UNREADABLE",
    "PROJECT_POLICY_INVALID","PROJECT_POLICY_SCOPE_MISMATCH","PROJECT_POLICY_NOT_PREPARED"})


@dataclass(frozen=True)
class ProjectExecutionConfig:
    """Project settings, not a scheduler or an independent rights determination.

    The 24-hour interval is a scheduling plan, not an elapsed-time run embargo.
    Smoke is explicitly one app; pilot is explicitly the existing eight apps.
    Execution is disabled by default. Deprecated administrative fields are
    readable metadata and are excluded from technical policy serialization.
    """
    policy_id: UUID | None = None
    operator: str | None = field(default=None,repr=False)
    execution_enabled: bool = False
    access_arrangement_confirmed: bool = field(default=False,repr=False,compare=False)
    access_basis_ref: str | None = field(default=None,repr=False,compare=False)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    purpose: str = "smoke"
    source_application_ids: tuple[str,...] = ()
    storefront: str = "us"
    sort_by: str = "mostrecent"
    config: IngestionConfig = IngestionConfig()
    schema_version: str = PROJECT_POLICY_SCHEMA_VERSION

    def __post_init__(self):
        if (self.schema_version!=PROJECT_POLICY_SCHEMA_VERSION or self.purpose not in {"smoke","pilot"}
                or type(self.execution_enabled) is not bool
                or type(self.source_application_ids) is not tuple
                or any(type(value) is not str or value not in PILOT_APPLICATION_IDS for value in self.source_application_ids)
                or len(set(self.source_application_ids))!=len(self.source_application_ids)
                or self.storefront!="us" or self.sort_by!="mostrecent" or type(self.config) is not IngestionConfig):
            raise LivePolicyError("PROJECT_POLICY_INVALID")
        if self.source_application_ids and ((self.purpose=="smoke" and len(self.source_application_ids)!=1)
                or (self.purpose=="pilot" and set(self.source_application_ids)!=PILOT_APPLICATION_IDS)):
            raise LivePolicyError("PROJECT_POLICY_INVALID")
        defaults=IngestionConfig()
        limits=IngestionConfig.from_dict(self.config.to_dict())
        if (limits.interval_hours!=24 or limits.retry_count!=0
                or limits.min_pages!=2 or limits.min_overlap_count!=20 or limits.min_overlap_ratio!=0.2
                or limits.max_pages>defaults.max_pages
                or limits.max_http_requests>defaults.max_http_requests or limits.max_response_bytes>defaults.max_response_bytes
                or limits.connect_timeout_seconds>defaults.connect_timeout_seconds or limits.read_timeout_seconds>defaults.read_timeout_seconds
                or limits.target_deadline_seconds>defaults.target_deadline_seconds or limits.global_spacing_seconds<defaults.global_spacing_seconds):
            raise LivePolicyError("PROJECT_POLICY_INVALID")
        if self.policy_id is not None and type(self.policy_id) is not UUID:
            raise LivePolicyError("PROJECT_POLICY_INVALID")
        if self.valid_from is not None or self.valid_until is not None:
            try:
                start,end=_aware(self.valid_from),_aware(self.valid_until)
                if not timedelta(0)<end-start<=timedelta(days=7): raise ValueError
            except Exception:
                raise LivePolicyError("PROJECT_POLICY_INVALID") from None

    def to_dict(self):
        value=asdict(self)
        value.pop("access_arrangement_confirmed",None)
        value.pop("access_basis_ref",None)
        value["policy_id"]=str(self.policy_id) if self.policy_id is not None else None
        value["valid_from"]=_stamp(self.valid_from); value["valid_until"]=_stamp(self.valid_until)
        value["source_application_ids"]=list(self.source_application_ids)
        value["config"]=self.config.to_dict()
        return value

    @classmethod
    def from_dict(cls,value):
        try:
            deprecated={"access_arrangement_confirmed","access_basis_ref"}
            required={item.name for item in fields(cls)}-deprecated
            if type(value) is not dict or not required<=set(value)<=required|deprecated: raise ValueError
            data={name:value[name] for name in required}
            if data["policy_id"] is not None: data["policy_id"]=UUID(data["policy_id"])
            for name in ("valid_from","valid_until"):
                if data[name] is not None: data[name]=_aware(datetime.fromisoformat(data[name].replace("Z","+00:00")))
            if type(data["source_application_ids"]) is not list: raise ValueError
            data["source_application_ids"]=tuple(data["source_application_ids"])
            data["config"]=IngestionConfig.from_dict(data["config"])
            return cls(**data)
        except Exception:
            raise LivePolicyError("PROJECT_POLICY_INVALID") from None


def project_policy_template(*,purpose="smoke",source_application_ids=None):
    ids=source_application_ids
    if ids is None: ids=("572688855",) if purpose=="smoke" else tuple(sorted(PILOT_APPLICATION_IDS))
    return ProjectExecutionConfig(purpose=purpose,source_application_ids=tuple(ids)).to_dict()


class ProjectExecutionPolicy:
    """Reusable scoped project policy; reload explicit JSON before each GET.

    Active-run binding is process-local safety state, not an authorization
    ledger. Durable run identity remains in the existing collection_run table.
    This class never creates receipts, enables targets or schedules execution.
    """
    def __init__(self,config=None,*,config_path=None):
        if (config is None)==(config_path is None) or config is not None and type(config) is not ProjectExecutionConfig:
            raise LivePolicyError("PROJECT_POLICY_INVALID")
        self._config=config
        self.config_path=Path(config_path) if config_path is not None else None
        self._runtime_engine=self._transport=self._deployment_config=self._readiness_check=None
        self._deployment_digest=None
        self._active=None
        self._begun=False
        self._closed=True
        self._mutex=threading.Lock()
        self.current_config()

    def current_config(self):
        if self.config_path is None:
            return replace(self._config)
        try:
            with self.config_path.open(encoding="utf-8") as handle: value=json.load(handle)
            return ProjectExecutionConfig.from_dict(value)
        except LivePolicyError:
            raise
        except Exception:
            raise LivePolicyError("PROJECT_POLICY_UNREADABLE") from None

    @property
    def operator(self):
        return self.current_config().operator

    @property
    def access_decision_ref(self):
        value=self.current_config()
        if value.policy_id is None: raise LivePolicyError("PROJECT_POLICY_INVALID")
        return f"{PROJECT_POLICY_SCHEMA_VERSION}:{value.policy_id}:sha256:{_digest(value.to_dict())}"

    def make_snapshot(self,*,application_id,source_application_id,target_id,software_revision,retention_policy_ref=None):
        from .parser import PARSER_VERSION
        value=self.current_config()
        if source_application_id not in value.source_application_ids:
            raise LivePolicyError("PROJECT_POLICY_SCOPE_MISMATCH")
        return ConfigSnapshot(application_id,source_application_id,target_id,software_revision,PARSER_VERSION,
            run_mode=RunMode.LIVE,access_decision_ref=self.access_decision_ref,retention_policy_ref=retention_policy_ref,config=value.config)

    def check_configuration(self,at):
        value=self.current_config()
        if not value.execution_enabled: raise LivePolicyError("PROJECT_EXECUTION_DISABLED")
        if value.policy_id is None or not _text(value.operator) or not value.source_application_ids:
            raise LivePolicyError("PROJECT_POLICY_INVALID")
        try: start,end,now=_aware(value.valid_from),_aware(value.valid_until),_aware(at)
        except LivePolicyError: raise LivePolicyError("PROJECT_POLICY_INVALID") from None
        if not start<=now<end: raise LivePolicyError("PROJECT_POLICY_OUTSIDE_VALIDITY")
        return value

    def prepare_runtime(self,engine,deployment_config,readiness_check,transport):
        with self._mutex:
            if not self._closed: raise LivePolicyError("PROJECT_POLICY_NOT_PREPARED")
            self._runtime_engine,self._deployment_config,self._readiness_check,self._transport=engine,deployment_config,readiness_check,transport
            self._deployment_digest=_deployment_binding(deployment_config)
            self._closed=False

    def validate_controller(self,engine,transport):
        if self._closed or engine is not self._runtime_engine or transport is not self._transport:
            raise LivePolicyError("PROJECT_POLICY_NOT_PREPARED")

    def validate(self,snapshot,batch_id,at,*,runtime_engine=None):
        value=self.check_configuration(at)
        if (self._closed or runtime_engine is not None and runtime_engine is not self._runtime_engine
                or _deployment_binding(self._deployment_config)!=self._deployment_digest):
            raise LivePolicyError("PROJECT_POLICY_NOT_PREPARED")
        if type(snapshot) is not ConfigSnapshot or snapshot.run_mode is not RunMode.LIVE:
            raise LivePolicyError("LIVE_SNAPSHOT_REQUIRED")
        if snapshot.access_decision_ref!=self.access_decision_ref:
            raise LivePolicyError("PROJECT_POLICY_CHANGED")
        if (snapshot.source_application_id not in value.source_application_ids or snapshot.config!=value.config
                or snapshot.storefront!=value.storefront or snapshot.sort_by!=value.sort_by
                or batch_id is not None and type(batch_id) is not UUID):
            raise LivePolicyError("PROJECT_POLICY_SCOPE_MISMATCH")
        if self._active is not None and (_digest(snapshot.to_dict())!=self._active["snapshot_digest"]
                or batch_id is not None and batch_id!=self._active["batch_id"]):
            raise LivePolicyError("PROJECT_POLICY_SCOPE_MISMATCH")

    def validate_target(self,snapshot,enabled,at):
        self.validate(snapshot,None,at)
        if enabled is not True: raise LivePolicyError("LIVE_TARGET_DISABLED")

    def validate_batch(self,snapshots,batch_id,at):
        value=self.check_configuration(at)
        if value.purpose!="pilot": raise LivePolicyError("PROJECT_SMOKE_ONE_APP_ONLY")
        if len(snapshots)!=8 or {item.source_application_id for item in snapshots}!=set(value.source_application_ids):
            raise LivePolicyError("PROJECT_POLICY_SCOPE_MISMATCH")
        for snapshot in snapshots: self.validate(snapshot,batch_id,at,runtime_engine=self._runtime_engine)

    def begin_execution(self,snapshot,batch_id,at,*,runtime_engine=None):
        with self._mutex:
            if self._active is not None: raise LivePolicyError("PROJECT_RUN_IN_PROGRESS")
            self.validate(snapshot,batch_id,at,runtime_engine=runtime_engine)
            self._active={"snapshot":snapshot,"snapshot_digest":_digest(snapshot.to_dict()),"batch_id":batch_id,"requests":0}
        try:
            self._readiness_check(snapshot)
            self._begun=True
        except Exception:
            self.finish_execution(snapshot,batch_id)
            raise

    def validate_run_identity(self,connection,snapshot,batch_id):
        from sqlalchemy import select
        from .models import CollectionRun
        run=CollectionRun.__table__
        if connection.scalar(select(run.c.id).where(run.c.batch_id==batch_id,run.c.target_id==snapshot.target_id).limit(1)) is not None:
            raise LivePolicyError("PROJECT_BATCH_ALREADY_USED")

    def before_http(self,snapshot,batch_id,at,*,runtime_engine,request_number,page_number):
        self.validate(snapshot,batch_id,at,runtime_engine=runtime_engine)
        if self._active is None or not self._begun: raise LivePolicyError("PROJECT_POLICY_NOT_PREPARED")
        if (request_number!=self._active["requests"]+1 or request_number>snapshot.config.max_http_requests
                or not 1<=page_number<=snapshot.config.max_pages):
            raise LivePolicyError("PROJECT_POLICY_SCOPE_MISMATCH")
        self._active["requests"]=request_number

    def validate_before_send(self,url,at):
        if self._active is None or not self._begun: raise LivePolicyError("PROJECT_POLICY_NOT_PREPARED")
        active=self._active
        self.validate(active["snapshot"],active["batch_id"],at,runtime_engine=self._runtime_engine)
        import re
        expected=rf"https://itunes\.apple\.com/us/rss/customerreviews/page=[1-9][0-9]*/id={active['snapshot'].source_application_id}/sortby=mostrecent/(json|xml)"
        if re.fullmatch(expected,url) is None: raise LivePolicyError("PROJECT_POLICY_SCOPE_MISMATCH")

    def remaining_seconds(self,at):
        return max(0.0,(_aware(self.current_config().valid_until)-_aware(at)).total_seconds())

    def finish_execution(self,snapshot,batch_id):
        with self._mutex:
            if self._active is not None and self._active["batch_id"]==batch_id:
                self._active=None
                self._begun=False

    def close(self):
        self._active=None; self._begun=False; self._closed=True


@contextmanager
def prepare_project_controller(engine,spool,*,policy=None,deployment_config=None,audit_engine=None,environ=None,
                               session_factory=None,now=None,clock=time.monotonic,sleep=time.sleep):
    """Reusable project workflow; no receipt, scheduler or automatic run.

    Each run checks actual deployment and target readiness afresh. The shared
    BoundedTransport retains global request spacing between successive runs.
    The final GET guard rechecks file-backed revocation after spacing sleeps.
    """
    if type(policy) is not ProjectExecutionPolicy: raise LivePolicyError("LIVE_MODE_DISABLED")
    at=now or (lambda:datetime.now(timezone.utc))
    policy.check_configuration(at())
    _deployment_preflight(engine,audit_engine,deployment_config,None,policy,spool,environ)
    controller=Controller(engine,None,spool,now=at,monotonic=clock,live_policy=policy)
    def readiness_check(snapshot):
        _deployment_preflight(engine,audit_engine,deployment_config,snapshot,policy,spool,environ)
        with engine.connect() as connection:
            with connection.begin(): controller._validate_target(connection,snapshot)
    transport=_PreparedTransport(policy,session_factory,clock,sleep,
        before_send=lambda url:policy.validate_before_send(url,controller._time()))
    controller.transport=transport
    policy.prepare_runtime(engine,deployment_config,readiness_check,transport)
    try: yield controller
    finally:
        policy.close(); transport.close()


__all__=["APPROVAL_SCHEMA_VERSION","LiveExecutionApproval","LiveExecutionPolicy","LivePolicyError",
         "approval_template","prepare_live_controller","PROJECT_POLICY_SCHEMA_VERSION","ProjectExecutionConfig",
         "ProjectExecutionPolicy","project_policy_template","prepare_project_controller"]
