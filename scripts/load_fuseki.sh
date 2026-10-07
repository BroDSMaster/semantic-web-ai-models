#!/usr/bin/env bash
# Add catalog data to the default graph. Never clears an existing dataset.
set -euo pipefail
cd "$(dirname "$0")/.."
catalog_endpoint="${1:-http://localhost:3030/aimodels/data}"
for catalog_file in res/ontology.ttl src/data/gold/models.ttl res/linked_output.nt res/dataset-metadata.ttl; do
  catalog_type="text/turtle"
  if [[ "$catalog_file" == *.nt ]]; then catalog_type="application/n-triples"; fi
  curl --fail --show-error --silent -X POST -H "Content-Type: $catalog_type" \
    --data-binary "@$catalog_file" "${catalog_endpoint}?default"
  echo "Loaded $catalog_file"
done
