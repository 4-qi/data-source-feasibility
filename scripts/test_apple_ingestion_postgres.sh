#!/usr/bin/env bash
# Create an isolated local PostgreSQL cluster; never consume an ambient DSN.
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/.." && pwd)
pg_bin=${APPLE_TEST_PG_BIN:-/usr/lib/postgresql/16/bin}
test_python=${APPLE_TEST_PYTHON:-python3}
# Historical default remains the Phase A database module. --full-suite delegates
# discovery to pytest; explicit paths following it replace default discovery.
full_suite=false
if [[ "${1:-}" == '--full-suite' ]]; then
  full_suite=true
  shift
fi
if [[ ! -x "$pg_bin/initdb" || ! -x "$pg_bin/pg_ctl" ]]; then
  echo 'PostgreSQL binaries unavailable; set APPLE_TEST_PG_BIN.' >&2
  exit 2
fi
cluster_root=$(mktemp -d /tmp/apple-phase-a-pg.XXXXXX)
cleanup() {
  "$pg_bin/pg_ctl" -D "$cluster_root/data" -m immediate stop >/dev/null 2>&1 || true
  rm -rf -- "$cluster_root"
}
trap cleanup EXIT
mkdir "$cluster_root/socket"
"$pg_bin/initdb" -D "$cluster_root/data" --auth-local=trust --auth-host=reject --encoding=UTF8 --locale=C >"$cluster_root/initdb.log"
# TCP is disabled. A unique private socket directory isolates this port number.
if ! "$pg_bin/pg_ctl" -D "$cluster_root/data" -l "$cluster_root/server.log" \
  -o "-k $cluster_root/socket -p 55439 -c listen_addresses='' -c timezone=UTC" -w start >/dev/null; then
  cat "$cluster_root/server.log" >&2
  exit 2
fi
"$pg_bin/createdb" -h "$cluster_root/socket" -p 55439 apple_phase_a_test
export APPLE_INGESTION_TEST_DSN="host=$cluster_root/socket port=55439 dbname=apple_phase_a_test"
export APPLE_INGESTION_DISPOSABLE=1
cd "$repo_root"
if "$full_suite"; then
  "$test_python" -m pytest "$@"
else
  "$test_python" -m pytest tests/test_apple_ingestion_database.py "$@"
fi
