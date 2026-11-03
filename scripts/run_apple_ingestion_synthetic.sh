#!/usr/bin/env bash
# Seven simulated days, private /tmp database, no real HTTP, no system services.
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/.." && pwd)
pg_bin=${APPLE_TEST_PG_BIN:-/usr/lib/postgresql/16/bin}
test_python=${APPLE_TEST_PYTHON:-python3}
output_root=${1:-}
if [[ -z "$output_root" || "$output_root" != /tmp/* || -e "$output_root" || -L "$output_root" ]]; then
  echo 'Supply a fresh absolute /tmp output directory.' >&2
  exit 2
fi
if [[ ! -x "$pg_bin/initdb" || ! -x "$pg_bin/pg_ctl" ]]; then
  echo 'PostgreSQL binaries unavailable; set APPLE_TEST_PG_BIN.' >&2
  exit 2
fi
cluster_root=$(mktemp -d /tmp/apple-synthetic-pg.XXXXXX)
cleanup() {
  "$pg_bin/pg_ctl" -D "$cluster_root/data" -m immediate stop >/dev/null 2>&1 || true
  rm -rf -- "$cluster_root"
}
trap cleanup EXIT
mkdir "$cluster_root/socket"
"$pg_bin/initdb" -D "$cluster_root/data" --auth-local=trust --auth-host=reject --encoding=UTF8 --locale=C >"$cluster_root/initdb.log"
if ! "$pg_bin/pg_ctl" -D "$cluster_root/data" -l "$cluster_root/server.log" \
    -o "-k $cluster_root/socket -p 55439 -c listen_addresses='' -c timezone=UTC" -w start >/dev/null; then
  cat "$cluster_root/server.log" >&2
  exit 2
fi
"$pg_bin/createdb" -h "$cluster_root/socket" -p 55439 apple_phase_a_rehearsal
cd "$repo_root"
"$test_python" -m feasibility.apple_ingestion.cli rehearse --disposable --initialize \
  --database-url "postgresql+psycopg:///apple_phase_a_rehearsal?host=$cluster_root/socket&port=55439" \
  --output "$output_root" --software-revision synthetic-uncommitted-phase-d
