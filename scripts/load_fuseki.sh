#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
fuseki_dataset="${1:-http://localhost:3030/aimodels}"
# POST merges into the default graph. Do not PUT each file: PUT replaces it.
for turtle_file in res/ontology.ttl src/data/gold/research.ttl res/dataset-metadata.ttl; do
  curl --fail-with-body --silent --show-error -X POST \
    -H 'Content-Type: text/turtle' --data-binary "@$turtle_file" "$fuseki_dataset/data?default"
done
curl --fail-with-body --silent --show-error -X POST \
  -H 'Content-Type: application/n-triples' --data-binary @res/linked_output.nt "$fuseki_dataset/data?default"
echo "Loaded ontology, research data, metadata and identity links into $fuseki_dataset."
