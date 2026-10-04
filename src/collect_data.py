"""Stage 2: snapshot OpenAlex works plus frequently occurring entities."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode

from common import BRONZE, WORK_FILTER, fetch_json, now, openalex_key, write_json

API = "https://api.openalex.org"


def collect(limit=200, search='"large language models"', enrich_limit=25):
    if not 1 <= limit <= 10000 or not 0 <= enrich_limit <= 200:
        raise ValueError("limit must be 1..10000 and enrich-limit 0..200")
    works, requests, warnings = [], [], []
    page, page_size = 1, min(100, limit)
    while len(works) < limit:
        params = {"search": search, "filter": WORK_FILTER,
                  "sort": "cited_by_count:desc", "per_page": page_size, "page": page}
        url = API + "/works"
        result = fetch_json(url, params, openalex=True)
        requests.append(url + "?" + urlencode(params))
        batch = result.get("results", [])
        if not batch:
            break
        works.extend(batch)
        print(f"Collected {min(len(works), limit)}/{limit} papers", flush=True)
        page += 1
    if not works:
        raise RuntimeError("OpenAlex returned no works; no files were changed")
    works = works[:limit]

    institutions = Counter(i["id"] for w in works for a in w.get("authorships", [])
                           for i in a.get("institutions", []) if i.get("id"))
    sources = Counter(s["id"] for w in works
                      if (s := (w.get("primary_location") or {}).get("source")) and s.get("id"))
    details = {"institutions": [], "sources": []}
    jobs = [(kind, ident) for kind, counter in [("institutions", institutions), ("sources", sources)]
            for ident, _ in counter.most_common(enrich_limit)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch_json, f"{API}/{kind}/{openalex_key(ident)}", openalex=True): (kind, ident)
                   for kind, ident in jobs}
        for future in as_completed(futures):
            kind, ident = futures[future]
            try:
                details[kind].append(future.result())
                requests.append(f"{API}/{kind}/{openalex_key(ident)}")
            except RuntimeError as exc:
                warnings.append({"entity": ident, "error": str(exc)})
    for kind in details:
        details[kind].sort(key=lambda entity: entity["id"])
    write_json(BRONZE / "openalex_works.json", works[:limit])
    write_json(BRONZE / "openalex_institutions.json", details["institutions"])
    write_json(BRONZE / "openalex_sources.json", details["sources"])
    manifest = {"retrieved_at": now(), "source": "OpenAlex", "license": "CC0-1.0 (OpenAlex metadata)",
                "search": search, "filter": WORK_FILTER, "sort": "cited_by_count:desc",
                "requested_limit": limit, "works": len(works[:limit]), "enrich_limit_per_kind": enrich_limit,
                "requests": sorted(requests), "warnings": warnings}
    write_json(BRONZE / "collection_manifest.json", manifest)
    print(f"Saved bronze snapshot: {manifest['works']} papers; {len(warnings)} enrichment warnings")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--search", default='"large language models"')
    parser.add_argument("--enrich-limit", type=int, default=25)
    args = parser.parse_args()
    collect(args.limit, args.search, args.enrich_limit)
