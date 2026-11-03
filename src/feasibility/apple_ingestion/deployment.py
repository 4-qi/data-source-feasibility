"""Explicit deployment preparation; no provisioning, network or import I/O.

Templates contain environment variable names, never credentials. Readiness is
not access authorization: the controller's live-policy layer remains the sole
authorization contract. Mutations require explicit opt-in and a caller-owned
maintenance transaction; this phase executes them only in disposable tests.
"""
from dataclasses import asdict, dataclass
from io import StringIO
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from sqlalchemy import event, text

from .db import create_db_engine, database_url
from .models import Base
from .normalizer import HASH_CONTRACT_VERSION
from .parser import PARSER_VERSION
from .permissions import RoleConfig, RUNTIME_UPDATE_COLUMNS, IDENTITY_TABLES, apply_permissions, permission_sql
from .seed import load_seed_manifest, seed_defaults

SCHEMA_VERSION='apple-ingestion-deployment/1'
REVISION='0001_apple_ingestion'
ROOT=Path(__file__).resolve().parents[3]


class DeploymentError(ValueError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)


def _exact(data,fields):
    if type(data) is not dict or set(data)!=set(fields):
        raise DeploymentError('INVALID_DEPLOYMENT_CONFIG')


def _env_name(value):
    if type(value) is not str or not re.fullmatch('[A-Z][A-Z0-9_]{0,127}',value):
        raise DeploymentError('INVALID_ENVIRONMENT_REFERENCE')


def _optional_text(value):
    if value is not None and (type(value) is not str or not value.strip() or '\x00' in value):
        raise DeploymentError('INVALID_DEPLOYMENT_CONFIG')


@dataclass(frozen=True)
class DatabaseConfig:
    owner_url_env: str
    runtime_url_env: str
    report_url_env: str
    transport: str
    tls_root_cert_env: str | None
    postgresql_major: int
    connect_timeout_seconds: int
    lock_timeout_ms: int
    statement_timeout_ms: int

    def __post_init__(self):
        for name in (self.owner_url_env,self.runtime_url_env,self.report_url_env):
            _env_name(name)
        if len({self.owner_url_env,self.runtime_url_env,self.report_url_env})!=3:
            raise DeploymentError('DISTINCT_ROLE_DSN_REFERENCES_REQUIRED')
        if self.transport not in {'unix_socket','tls_verify_full'}:
            raise DeploymentError('UNSAFE_DATABASE_TRANSPORT')
        if self.tls_root_cert_env is not None:
            _env_name(self.tls_root_cert_env)
        if self.transport=='tls_verify_full' and self.tls_root_cert_env is None:
            raise DeploymentError('TLS_ROOT_CERT_REFERENCE_REQUIRED')
        values=(self.postgresql_major,self.connect_timeout_seconds,self.lock_timeout_ms,self.statement_timeout_ms)
        if any(type(value) is not int or value<=0 for value in values):
            raise DeploymentError('INVALID_DATABASE_LIMITS')
        if not self.lock_timeout_ms<=self.statement_timeout_ms<=300000:
            raise DeploymentError('INVALID_DATABASE_LIMITS')


@dataclass(frozen=True)
class RetentionConfig:
    state: str
    owner: str | None
    duration_days: int | None
    policy_ref: str | None
    backup_handling_ref: str | None
    export_handling_ref: str | None
    expiry_review_ref: str | None
    mode: str = 'finite_days'
    arrangement_confirmed: bool = False

    def __post_init__(self):
        if self.state not in {'pending','documented'}:
            raise DeploymentError('INVALID_RETENTION_STATE')
        if type(self.mode) is not str or self.mode not in {'finite_days','long_term'} or type(self.arrangement_confirmed) is not bool:
            raise DeploymentError('INVALID_RETENTION_MODE_OR_CONFIRMATION')
        for name in ('owner','policy_ref','backup_handling_ref','export_handling_ref','expiry_review_ref'):
            _optional_text(getattr(self,name))
        if self.duration_days is not None and (type(self.duration_days) is not int or self.duration_days<=0):
            raise DeploymentError('FINITE_RETENTION_REQUIRED')
        if self.mode=='long_term' and self.duration_days is not None:
            raise DeploymentError('LONG_TERM_DURATION_MUST_BE_NULL')
        if self.state=='documented' and not self.technical_complete:
            raise DeploymentError('INCOMPLETE_RETENTION_CONFIG')

    @property
    def technical_complete(self):
        return (self.state=='documented'
            and (self.mode=='long_term' or self.duration_days is not None)
            and all(getattr(self,name) is not None for name in (
                'owner','policy_ref','backup_handling_ref','export_handling_ref','expiry_review_ref')))

    @property
    def complete(self):
        # Legacy finite-day completeness stays unchanged. Long-term mode adds
        # an explicit applicable-arrangement confirmation, not a live approval.
        return self.technical_complete and (self.mode=='finite_days' or self.arrangement_confirmed)


@dataclass(frozen=True)
class DiagnosticsConfig:
    spool_path_env: str
    operator: str | None

    def __post_init__(self):
        _env_name(self.spool_path_env)
        _optional_text(self.operator)


@dataclass(frozen=True)
class DeploymentConfig:
    schema_version: str
    database: DatabaseConfig
    roles: RoleConfig
    retention: RetentionConfig
    diagnostics: DiagnosticsConfig

    def __post_init__(self):
        if (self.schema_version!=SCHEMA_VERSION or type(self.database) is not DatabaseConfig
                or type(self.roles) is not RoleConfig or type(self.retention) is not RetentionConfig
                or type(self.diagnostics) is not DiagnosticsConfig or self.roles.schema!='public'):
            raise DeploymentError('INVALID_DEPLOYMENT_CONFIG')

    @classmethod
    def from_dict(cls,value):
        _exact(value,('schema_version','database','roles','retention','diagnostics'))
        nested={}
        for name,kind in [('database',DatabaseConfig),('roles',RoleConfig),('retention',RetentionConfig),('diagnostics',DiagnosticsConfig)]:
            data=value[name]
            if name=='retention':
                optional={'mode','arrangement_confirmed'}
                fields=set(kind.__dataclass_fields__)
                if type(data) is not dict or not fields-optional<=set(data)<=fields:
                    raise DeploymentError('INVALID_DEPLOYMENT_CONFIG')
                data={'mode':'finite_days','arrangement_confirmed':False,**data}
            else:
                _exact(data,kind.__dataclass_fields__)
            try:
                nested[name]=kind(**data)
            except DeploymentError:
                raise
            except Exception:
                raise DeploymentError('INVALID_DEPLOYMENT_CONFIG') from None
        return cls(schema_version=value['schema_version'],**nested)

    def to_dict(self):
        return asdict(self)


def load_config(path):
    try:
        with Path(path).open(encoding='utf-8') as handle:
            return DeploymentConfig.from_dict(json.load(handle))
    except DeploymentError:
        raise
    except Exception:
        raise DeploymentError('DEPLOYMENT_CONFIG_UNREADABLE') from None


def _endpoint(url):
    # Deliberately strict: no host/socket/port aliases are silently accepted.
    return (url.drivername,url.database,url.host,url.port,url.query.get('host'),url.query.get('port'))


def deployment_engine(config,role,*,environ=None):
    """Create, do not connect. Never fall back to ambient default/shared DSNs."""
    environment=os.environ if environ is None else environ
    names={'owner':(config.database.owner_url_env,config.roles.maintenance_role),
        'runtime':(config.database.runtime_url_env,config.roles.runtime_role),
        'report':(config.database.report_url_env,config.roles.report_role)}
    if role not in names:
        raise DeploymentError('UNKNOWN_DEPLOYMENT_ROLE')
    reference,expected_user=names[role]
    supplied=environment.get(reference)
    if not supplied:
        raise DeploymentError('EXPLICIT_ROLE_DATABASE_URL_REQUIRED')
    try:
        url=database_url(supplied)
        if url.username!=expected_user or not url.database:
            raise ValueError
        query=dict(url.query)
        if config.database.transport=='unix_socket':
            host=query.get('host')
            if (url.host is not None or type(host) is not str or not Path(host).is_absolute()
                    or ',' in host or '..' in Path(host).parts or set(query)-{'host','port'}):
                raise ValueError
        else:
            if (not url.host or ',' in url.host or set(query)-{'sslmode','sslrootcert'}
                    or query.get('sslmode','verify-full')!='verify-full'):
                raise ValueError
            certificate=environment.get(config.database.tls_root_cert_env)
            if (type(certificate) is not str or not Path(certificate).is_absolute()
                    or not Path(certificate).is_file() or query.get('sslrootcert',certificate)!=certificate):
                raise ValueError
            query.update(sslmode='verify-full',sslrootcert=certificate)
        for other_reference,other_user in names.values():
            other_supplied=environment.get(other_reference)
            if not other_supplied:
                continue
            other=database_url(other_supplied)
            allowed={'host','port'} if config.database.transport=='unix_socket' else {'sslmode','sslrootcert'}
            if other.username!=other_user or _endpoint(other)!=_endpoint(url) or set(other.query)-allowed:
                raise ValueError
            if config.database.transport=='tls_verify_full' and (
                    other.query.get('sslmode','verify-full')!='verify-full'
                    or other.query.get('sslrootcert',certificate)!=certificate):
                raise ValueError
        query['connect_timeout']=str(config.database.connect_timeout_seconds)
        engine=create_db_engine(url.set(query=query))
    except Exception:
        raise DeploymentError('UNSAFE_OR_MISMATCHED_ROLE_DATABASE_URL') from None

    @event.listens_for(engine,'connect')
    def _timeouts(driver,_record):
        previous=driver.autocommit
        driver.autocommit=True
        try:
            with driver.cursor() as cursor:
                cursor.execute("SELECT set_config('search_path','public',false)")
                cursor.execute("SELECT set_config('lock_timeout',%s,false)",(f'{config.database.lock_timeout_ms}ms',))
                cursor.execute("SELECT set_config('statement_timeout',%s,false)",(f'{config.database.statement_timeout_ms}ms',))
        finally:
            driver.autocommit=previous
    return engine


def initialization_plan(config):
    """Reviewable SQL only. Does not read env credentials or contact PostgreSQL."""
    from alembic import command
    from alembic.config import Config
    stream=StringIO()
    alembic=Config(str(ROOT/'alembic.ini'),output_buffer=stream)
    alembic.set_main_option('script_location',str(ROOT/'migrations'))
    command.upgrade(alembic,REVISION,sql=True)
    def quoted(name):
        return '"'+name.replace('"','""')+'"'
    roles=[f'CREATE ROLE {quoted(role)} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;'
        for role in (config.roles.maintenance_role,config.roles.runtime_role,config.roles.report_role)]
    return {'schema_version':SCHEMA_VERSION,'execution':'review_only','live_authorized':False,
        'revision':REVISION,'administrator_role_sql':roles,
        'ownership_requirement':'maintenance role must own database or public schema; runtime/report own neither',
        'migration_sql':stream.getvalue(),'permission_sql':list(permission_sql(config.roles)),
        'seed':{'applications':8,'storefront':'us','sort_by':'mostrecent','new_targets_enabled':False},
        'retention_state':config.retention.state,'secret_values_included':False}


def _owner_transaction(connection,config):
    from sqlalchemy.engine import Connection
    if (not isinstance(connection,Connection) or not connection.in_transaction() or connection.dialect.name!='postgresql'
            or connection.get_execution_options().get('isolation_level')=='AUTOCOMMIT'
            or connection.connection.driver_connection.autocommit):
        raise DeploymentError('CALLER_OWNED_MAINTENANCE_TRANSACTION_REQUIRED')
    row=connection.execute(text('''SELECT current_user,session_user,r.rolsuper,r.rolcreatedb,r.rolcreaterole,
        r.rolreplication,r.rolbypassrls FROM pg_roles r WHERE r.rolname=current_user''')).one()
    if row[0]!=config.roles.maintenance_role or row[1]!=row[0] or any(row[2:]):
        raise DeploymentError('ACTUAL_NONADMIN_MAINTENANCE_LOGIN_REQUIRED')
    if not connection.execute(text("SELECT pg_has_role(current_user,nspowner,'USAGE') FROM pg_namespace WHERE nspname='public'")).scalar_one():
        raise DeploymentError('MAINTENANCE_SCHEMA_OWNERSHIP_REQUIRED')
    if connection.execute(text('SELECT current_schema()')).scalar_one()!='public':
        raise DeploymentError('PUBLIC_SCHEMA_REQUIRED')


def initialize_database(connection,config,*,execute=False):
    """Migrate/seed only when explicitly opted in; never commits caller work."""
    if execute is not True:
        return initialization_plan(config)
    _owner_transaction(connection,config)
    from alembic import command
    from alembic.config import Config
    alembic=Config(str(ROOT/'alembic.ini'))
    alembic.set_main_option('script_location',str(ROOT/'migrations'))
    alembic.attributes['connection']=connection
    command.upgrade(alembic,REVISION)
    seeded=seed_defaults(connection,ROOT/'results/mainstream/app_sample_manifest.json')
    return {'revision':REVISION,'application_count':len(seeded.application_ids),'target_count':len(seeded.target_ids),
        'live_authorized':False}


def grant_permissions(connection,config,*,execute=False):
    if execute is not True:
        return tuple(permission_sql(config.roles))
    _owner_transaction(connection,config)
    apply_permissions(connection,config.roles)
    return {'grants_applied':True,'caller_must_commit':True,'live_authorized':False}


def diagnostics_probe(config,*,environ=None,execute=False):
    """Default: read-only path/mode/access checks. Explicit probe uses no spool event."""
    environment=os.environ if environ is None else environ
    supplied=environment.get(config.diagnostics.spool_path_env)
    blockers=[]
    path=Path(supplied) if type(supplied) is str else None
    if (path is None or not path.is_absolute() or '..' in path.parts
            or path.parent.resolve()!=path.parent or not path.parent.is_dir()
            or any((p/'.git').is_file() or (p/'.git/HEAD').is_file() for p in path.parents)):
        blockers.append('DIAGNOSTIC_PATH_PENDING_OR_UNSAFE')
    else:
        parent=path.parent.stat()
        if parent.st_uid!=os.getuid() or stat.S_IMODE(parent.st_mode)!=0o700:
            blockers.append('DIAGNOSTIC_DIRECTORY_MUST_BE_PRIVATE')
        if not os.access(path.parent,os.W_OK|os.X_OK):
            blockers.append('DIAGNOSTIC_DIRECTORY_NOT_WRITABLE')
        if path.is_symlink() or (path.exists() and (not path.is_file() or path.stat().st_uid!=os.getuid()
                or stat.S_IMODE(path.stat().st_mode)!=0o600 or path.stat().st_nlink!=1)):
            blockers.append('DIAGNOSTIC_FILE_MUST_BE_PRIVATE')
    if config.diagnostics.operator is None:
        blockers.append('DIAGNOSTIC_OPERATOR_PENDING')
    result={'ready':not blockers,'blockers':blockers,'write_probe_executed':False,
        'durability_guaranteed':False,'live_authorized':False}
    if execute is True and not blockers:
        fd,name=None,None
        try:
            fd,name=tempfile.mkstemp(prefix='.apple-deployment-probe-',dir=path.parent)
            os.write(fd,b'{"deployment_write_probe":true,"contains_review_text":false}\n')
            os.fsync(fd)
            parent_fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
            result['write_probe_executed']=True
        except Exception:
            result['ready']=False
            result['blockers'].append('DIAGNOSTIC_WRITE_PROBE_FAILED')
        finally:
            if fd is not None:
                os.close(fd)
            if name is not None:
                try:
                    os.unlink(name)
                except OSError:
                    result['ready']=False
                    result['blockers'].append('DIAGNOSTIC_PROBE_CLEANUP_FAILED')
    return result


def _preflight(connection,config,*,for_live=False,environ=None,runtime_connection=None):
    """SELECT-only readiness. Does not validate/issue an ApprovedLivePolicy."""
    blockers=[]
    server=connection.execute(text("SELECT current_setting('server_version_num')::integer,current_setting('TimeZone')")).one()
    if server[0]//10000!=config.database.postgresql_major:
        blockers.append('POSTGRESQL_MAJOR_MISMATCH')
    if server[1]!='UTC':
        blockers.append('UTC_SESSION_REQUIRED')
    if connection.execute(text('SELECT current_schema()')).scalar_one()!='public':
        blockers.append('PUBLIC_SCHEMA_REQUIRED')
    if connection.engine.echo or not connection.engine.hide_parameters:
        blockers.append('SAFE_SQL_LOGGING_REQUIRED')
    tables=set(connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars())
    schema_ok=tables==set(Base.metadata.tables)|{'alembic_version'}
    if not schema_ok:
        blockers.append('SCHEMA_TABLE_SET_MISMATCH')
    revision=None
    if 'alembic_version' in tables:
        revisions=connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
        revision=revisions[0] if len(revisions)==1 else None
    if revision!=REVISION:
        blockers.append('MIGRATION_REVISION_MISMATCH')
    roles=(config.roles.maintenance_role,config.roles.runtime_role,config.roles.report_role)
    for role in roles:
        info=connection.execute(text('''SELECT oid,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,
            rolcanlogin FROM pg_roles WHERE rolname=:role'''),dict(role=role)).one_or_none()
        if info is None or any(info[1:6]) or not info[6]:
            blockers.append('NONADMIN_LOGIN_ROLES_REQUIRED')
        elif role!=config.roles.maintenance_role:
            if connection.execute(text('SELECT count(*) FROM pg_auth_members WHERE member=:oid'),dict(oid=info[0])).scalar_one():
                blockers.append('CONSUMER_ROLE_MEMBERSHIPS_FORBIDDEN')
            if connection.execute(text('SELECT datdba=:oid FROM pg_database WHERE datname=current_database()'),dict(oid=info[0])).scalar_one():
                blockers.append('CONSUMER_DATABASE_OWNERSHIP_FORBIDDEN')
    seeded=False
    if schema_ok:
        expected={row.source_application_id for row in load_seed_manifest(ROOT/'results/mainstream/app_sample_manifest.json')}
        apps=connection.execute(text("SELECT source_application_id FROM application WHERE source='apple_app_store'")).scalars().all()
        count=connection.execute(text("SELECT count(*) FROM collection_target WHERE storefront='us' AND sort_by='mostrecent'")).scalar_one()
        seeded=len(apps)==8 and set(apps)==expected and count==8
        if not seeded:
            blockers.append('EIGHT_APPLICATION_SEED_REQUIRED')
        owners=connection.execute(text("""SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            JOIN pg_roles r ON r.oid=c.relowner WHERE n.nspname='public' AND c.relkind IN ('r','S') AND r.rolname<>:owner"""),dict(owner=config.roles.maintenance_role)).scalar_one()
        if owners:
            blockers.append('MAINTENANCE_OBJECT_OWNERSHIP_REQUIRED')
        trigger=connection.execute(text("SELECT count(*) FROM pg_trigger WHERE tgname='collection_run_identity_is_immutable' AND tgenabled='O'")).scalar_one()
        if trigger!=1:
            blockers.append('IMMUTABLE_RUN_TRIGGER_REQUIRED')
        for table in Base.metadata.tables:
            for role in (config.roles.runtime_role,config.roles.report_role):
                if connection.execute(text("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=:role)"),dict(role=role)).scalar_one():
                    if not connection.execute(text("SELECT has_table_privilege(:role,:table,'SELECT')"),dict(role=role,table='public.'+table)).scalar_one():
                        blockers.append('CONSUMER_SELECT_GRANTS_MISSING')
            if connection.execute(text("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=:role)"),dict(role=config.roles.runtime_role)).scalar_one():
                if not connection.execute(text("SELECT has_table_privilege(:role,:table,'INSERT')"),dict(role=config.roles.runtime_role,table='public.'+table)).scalar_one():
                    blockers.append('RUNTIME_INSERT_GRANTS_MISSING')
        runtime=config.roles.runtime_role
        if connection.execute(text("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=:role)"),dict(role=runtime)).scalar_one():
            if connection.execute(text("SELECT has_table_privilege(:role,'public.review_version','UPDATE,DELETE')"),dict(role=runtime)).scalar_one():
                blockers.append('VERSION_APPEND_ONLY_PRIVILEGES_REQUIRED')
        for role in (config.roles.runtime_role,config.roles.report_role):
            exists=connection.execute(text('SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=:role)'),dict(role=role)).scalar_one()
            if not exists:
                continue
            if connection.execute(text("SELECT has_schema_privilege(:role,'public','CREATE')"),dict(role=role)).scalar_one():
                blockers.append('CONSUMER_SCHEMA_CREATE_FORBIDDEN')
            for table in Base.metadata.tables.values():
                qualified='public.'+table.name
                if connection.execute(text("SELECT has_table_privilege(:role,:table,'DELETE,TRUNCATE')"),dict(role=role,table=qualified)).scalar_one():
                    blockers.append('CONSUMER_DELETE_OR_TRUNCATE_FORBIDDEN')
                allowed=set(RUNTIME_UPDATE_COLUMNS.get(table.name,())) if role==config.roles.runtime_role else set()
                for column in table.columns:
                    permitted=connection.execute(text("SELECT has_column_privilege(:role,:table,:column,'UPDATE')"),
                        dict(role=role,table=qualified,column=column.name)).scalar_one()
                    if permitted!=(column.name in allowed):
                        blockers.append('EXACT_RUNTIME_OR_REPORT_UPDATE_GRANTS_REQUIRED')
                if role==config.roles.report_role and connection.execute(text("SELECT has_any_column_privilege(:role,:table,'INSERT')"),dict(role=role,table=qualified)).scalar_one():
                    blockers.append('REPORT_WRITE_PRIVILEGES_FORBIDDEN')
            if role==config.roles.runtime_role:
                for name in IDENTITY_TABLES:
                    if not connection.execute(text("SELECT has_sequence_privilege(:role,:sequence,'USAGE')"),dict(role=role,sequence=f'public.{name}_id_seq')).scalar_one():
                        blockers.append('RUNTIME_SEQUENCE_USAGE_REQUIRED')
    database_ready=not blockers
    diagnostics=diagnostics_probe(config,environ=environ)
    runtime_verified=False
    if runtime_connection is not None:
        actual=runtime_connection.execute(text('SELECT current_user,session_user,current_setting(\'TimeZone\'),current_database()')).one()
        runtime_verified=actual[0]==actual[1]==config.roles.runtime_role and actual[2]=='UTC'
        current_database=connection.execute(text('SELECT current_database()')).scalar_one()
        runtime_verified=runtime_verified and actual[3]==current_database and _endpoint(runtime_connection.engine.url)==_endpoint(connection.engine.url)
        runtime_verified=runtime_verified and not runtime_connection.engine.echo and runtime_connection.engine.hide_parameters
        runtime_verified=runtime_verified and runtime_connection.execute(text('SELECT current_schema()')).scalar_one()=='public'
        if not runtime_verified:
            blockers.append('ACTUAL_RUNTIME_LOGIN_REQUIRED')
        else:
            for name in Base.metadata.tables:
                runtime_connection.execute(text(f'SELECT 1 FROM public.{name} LIMIT 0'))
    if for_live:
        if not runtime_verified:
            blockers.append('RUNTIME_LOGIN_NOT_VERIFIED')
        if not config.retention.complete:
            blockers.append('RETENTION_DECISION_PENDING')
        if config.retention.mode=='long_term' and not config.retention.arrangement_confirmed:
            blockers.append('LONG_TERM_ARRANGEMENT_UNCONFIRMED')
        blockers.extend(diagnostics['blockers'])
    return {'schema_version':SCHEMA_VERSION,'read_only':True,'for_live':bool(for_live),
        'live_ready':bool(for_live) and not blockers,
        'status':'blocked' if blockers else 'deployment_ready_policy_unchecked',
        'ready':not blockers,'database_ready':database_ready,'retention_ready':config.retention.complete,
        'blockers':sorted(set(blockers)),'revision':revision,'postgresql_major':server[0]//10000,
        'seeded_eight_applications':seeded,'retention_documented':config.retention.technical_complete,
        'retention_technical_ready':config.retention.technical_complete,
        'retention_arrangement_confirmed':config.retention.arrangement_confirmed,
        'retention':asdict(config.retention),
        'diagnostics':diagnostics,'parser_version':PARSER_VERSION,'hash_contract_version':HASH_CONTRACT_VERSION,
        'db_timeout_profile':{'configured_session_lock_ms':config.database.lock_timeout_ms,
            'configured_session_statement_ms':config.database.statement_timeout_ms,
            'application_session_fixed_lock_ms':5000,'application_session_fixed_statement_ms':10000,
            'page_transaction_default_lock_ms':5000,'page_transaction_default_statement_ms':30000,
            'arbitrary_override_propagated_through_pipeline':False},
        'runtime_login_verified':runtime_verified,
        'scope':{'source':'apple_app_store','storefront':'us','sort_by':'mostrecent','application_count':8 if seeded else 0,
            'source_application_ids':sorted(expected) if seeded else []},
        'authorization_owner':'live.ProjectExecutionPolicy',
        'legacy_authorization_owner':'live.LiveExecutionPolicy','live_authorized':False,
        'live_policy_checked':False,'real_http_performed':False}


def preflight(connection,config,*,for_live=False,environ=None,runtime_connection=None):
    """Safe SELECT-only report; pass an actual runtime login for live readiness.

    A ready deployment is not authorized execution. ProjectExecutionPolicy must
    separately validate confirmed project conditions, scope/window and limits.
    The legacy single-run API remains compatible but is not required.
    Neither connection is committed, rolled back or replaced by this function.
    """
    try:
        return _preflight(connection,config,for_live=for_live,environ=environ,runtime_connection=runtime_connection)
    except DeploymentError:
        raise
    except Exception:
        raise DeploymentError('DATABASE_PREFLIGHT_UNAVAILABLE') from None


__all__=['DeploymentError','DeploymentConfig','DatabaseConfig','RetentionConfig','DiagnosticsConfig',
    'load_config','deployment_engine','initialization_plan','initialize_database',
    'grant_permissions','diagnostics_probe','preflight']
