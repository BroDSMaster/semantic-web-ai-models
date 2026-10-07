#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
fuseki_binary="$PWD/tools/apache-jena-fuseki-6.2.0/fuseki-server"
if [[ ! -f "$fuseki_binary" ]]; then
  echo "Install Fuseki into tools/; see docs/FUSEKI.md." >&2
  exit 1
fi
mkdir -p run/tdb2-models run/fuseki-models
exec env -u JAVA_HOME FUSEKI_BASE="$PWD/run/fuseki-models" "$fuseki_binary" \
  --localhost --port="${FUSEKI_PORT:-3030}" --conf="$PWD/res/fuseki-config.ttl"
