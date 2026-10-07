"""GET public model/endpoint metadata and source documents. Never performs inference."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, quote

from .common import BRONZE, RES, atomic_write, digest, fetch, now, read_json, write_json

CATALOG_URL = "https://openrouter.ai/api/v1/models"


def validate_catalog(payload):
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("Catalog must contain a non-empty data list; previous snapshot is preserved")
    if any(not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"] for row in rows):
        raise ValueError("Catalog row missing a string model ID")
    return rows


def validate_endpoints(payload):
    data = payload.get("data") if isinstance(payload, dict) else None
    rows = data.get("endpoints") if isinstance(data, dict) else None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Endpoint schema changed: expected data.endpoints list of objects")
    return rows


def fetch_catalog(fetcher=fetch):
    url, seen, rows, documents = CATALOG_URL, set(), {}, []
    while url:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "openrouter.ai" or parsed.path != "/api/v1/models" or url in seen:
            raise ValueError("Unsafe or cyclic catalog pagination link")
        seen.add(url)
        content = fetcher(url)
        payload = json.loads(content)
        for model in validate_catalog(payload):
            rows[model["id"]] = model
        checksum = digest(content)
        filename = "documents/openrouter-page-" + checksum + ".json"
        atomic_write(BRONZE / filename, content)
        documents.append({"url": url, "sha256": checksum, "retrieved_at": now(), "file": filename})
        links = payload.get("links") or {}
        next_url = links.get("next") if isinstance(links, dict) else None
        url = urljoin(CATALOG_URL, next_url) if next_url else None
    return {"data": list(rows.values())}, documents


def endpoint_url(model):
    # Catalog details can point at the paid canonical model even for :free
    # and :batch variants. Query the exact listing ID to avoid mixing prices.
    url = CATALOG_URL + "/" + quote(model["id"], safe="/") + "/endpoints"
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "openrouter.ai" or not parsed.path.startswith("/api/v1/models/") or not parsed.path.endswith("/endpoints"):
        raise ValueError("Unsafe endpoint link")
    return url


def collect(endpoint_limit=None, workers=6, offline=False):
    if offline:
        manifest = read_json(BRONZE / "manifest.json")
        validate_catalog(read_json(BRONZE / manifest.get("catalog_file", "openrouter_models.json")))
        print("Offline: preserving existing snapshots")
        return manifest
    if not 1 <= workers <= 12 or (endpoint_limit is not None and endpoint_limit < 0):
        raise ValueError("workers must be 1..12 and endpoint-limit nonnegative")
    catalog, docs = fetch_catalog()
    retrieved = now()
    manifest = {"retrieved_at": retrieved, "catalog_url": CATALOG_URL, "documents": docs,
                "warnings": [], "models": len(catalog["data"]), "endpoints": 0,
                "optional_artificial_analysis": "not requested; embedded OpenRouter benchmark records are collected"}
    # Validate entire catalog before committing any new current snapshot.
    endpoints = {}
    models = sorted(catalog["data"], key=lambda m: ("opus" not in m["id"].lower(), m["id"]))
    if endpoint_limit is not None:
        models = models[:endpoint_limit]

    def one(model):
        url = endpoint_url(model)
        content = fetch(url)
        payload = json.loads(content)
        validate_endpoints(payload)
        checksum = digest(content)
        filename = "documents/endpoint-" + checksum + ".json"
        atomic_write(BRONZE / filename, content)
        return model["id"], payload, {"url": url, "sha256": checksum, "retrieved_at": now(), "file": filename}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, m): m["id"] for m in models}
        for index, future in enumerate(as_completed(futures), 1):
            model_id = futures[future]
            try:
                key, payload, document = future.result()
                endpoints[key] = payload
                manifest["documents"].append(document)
                manifest["endpoints"] += len(payload["data"]["endpoints"])
            except (RuntimeError, ValueError) as exc:
                manifest["warnings"].append({"model_id": model_id, "error": str(exc)})
            if index % 40 == 0 or index == len(models):
                print(f"Endpoints {index}/{len(models)}; {manifest['endpoints']} provider entries", flush=True)
    sources = read_json(RES / "sources.json")
    for source in sources:
        try:
            content = fetch(source["url"])
            filename = "documents/" + source["id"] + "-" + digest(content) + ".html"
            atomic_write(BRONZE / filename, content)
            manifest["documents"].append({**source, "file": filename, "sha256": digest(content), "retrieved_at": now()})
        except RuntimeError as exc:
            manifest["warnings"].append({"source_id": source["id"], "error": str(exc)})
    # Readers use immutable aggregate files referenced by the manifest. An
    # interrupted recollection cannot mix a new catalog with old endpoints.
    catalog_file = "snapshots/catalog-" + digest(catalog) + ".json"
    endpoints_file = "snapshots/endpoints-" + digest(endpoints) + ".json"
    write_json(BRONZE / catalog_file, catalog)
    write_json(BRONZE / endpoints_file, endpoints)
    manifest.update({"catalog_file": catalog_file, "endpoints_file": endpoints_file})
    write_json(BRONZE / "openrouter_models.json", catalog)
    write_json(BRONZE / "openrouter_endpoints.json", endpoints)
    write_json(BRONZE / "manifest.json", manifest)
    print(f"Saved {manifest['models']} models, {manifest['endpoints']} endpoint entries, {len(manifest['warnings'])} warnings")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint-limit", type=int, default=None, help="default: enrich every catalog model")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    collect(args.endpoint_limit, args.workers, args.offline)


if __name__ == "__main__":
    main()
