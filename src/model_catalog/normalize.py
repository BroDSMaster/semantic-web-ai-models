"""Normalize source-specific offerings; never guess equivalence from names."""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json

from .common import BRONZE, RES, digest, read_json, uri, write_json, write_tables

DEVELOPERS = {"openai": ("OpenAI", "GPT"), "anthropic": ("Anthropic", "Claude"),
              "google": ("Google", "Gemini"), "meta-llama": ("Meta", "Llama"),
              "qwen": ("Alibaba", "Qwen"), "minimax": ("MiniMax", "MiniMax"),
              "z-ai": ("Z.AI", "GLM"), "mistralai": ("Mistral AI", "Mistral"),
              "x-ai": ("xAI", "Grok"), "deepseek": ("DeepSeek", "DeepSeek"),
              "moonshotai": ("Moonshot AI", "Kimi"), "cohere": ("Cohere", "Command")}
TOKEN_CATEGORIES = {"prompt", "completion", "input_cache_read", "input_cache_write", "input_cache_write_1h"}
UNITS = {"request": "request", "image": "image", "web_search": "search", "internal_reasoning": "unknown"}
TABLES = ["models", "families", "organizations", "offerings", "prices", "capabilities", "modalities",
          "observations", "evaluations", "benchmarks", "reviews", "documents", "external_links", "unmatched"]


def number(value):
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except InvalidOperation:
        return None


def normalize(catalog, endpoints, manifest, official_facts=None, reviews=None, model_cards=None):
    tables = {key: [] for key in TABLES}
    index = {key: {} for key in TABLES}
    timestamp = manifest["retrieved_at"]
    catalog_url = manifest["catalog_url"]
    source_docs = {d["url"]: d for d in manifest.get("documents", [])}

    def add(table, row):
        index[table][row["id"]] = row
        return row["id"]

    def document(url, name="", kind="catalog"):
        source = source_docs.get(url, {})
        observed = source.get("retrieved_at", timestamp)
        ident = uri("source-document", digest([url, source.get("sha256", observed)]))
        add("documents", {"id": ident, "url": url, "name": name or source.get("name", url),
                          "kind": source.get("kind", kind), "retrieved_at": observed,
                          "sha256": source.get("sha256", ""), "snapshot_file": source.get("file", "")})
        return ident

    def org(key, name):
        ident = uri("organization", key)
        add("organizations", {"id": ident, "name": name})
        return ident

    def observe(subject, predicate, value, doc, resource=False, datatype="string"):
        if value is None or value == "":
            return
        ident = uri("observation", digest([subject, predicate, value, doc]))
        add("observations", {"id": ident, "subject_id": subject, "predicate": predicate,
                             "value": str(value), "value_kind": "resource" if resource else "literal",
                             "datatype": datatype, "document_id": doc,
                             "observed_at": index["documents"][doc]["retrieved_at"]})

    def prices(offering, raw, doc, *, per_million=False, conditions="", tier="base", min_prompt_tokens=None):
        discount = Decimal(str((raw or {}).get("discount") if (raw or {}).get("discount") is not None else 0))
        if not discount.is_finite() or discount > 1:
            raise ValueError("Pricing discount must be finite and at most 1")
        if discount:
            conditions = (conditions + "; " if conditions else "") + f"Source discount {discount}; effective price = raw price * (1 - discount)."
        overrides = (raw or {}).get("overrides") or []
        if overrides:
            conditions = (conditions + "; " if conditions else "") + "Base rates; context/other overrides apply, see additional price records."
        for category, value in (raw or {}).items():
            amount = number(value)
            if amount is None or category in {"discount"}:
                continue
            unit = "million_tokens" if category in TOKEN_CATEGORIES else UNITS.get(category, "unknown")
            converted = amount * 1000000 if unit == "million_tokens" and not per_million else amount
            converted *= 1 - discount
            ident = uri("price", digest([offering, category, str(converted), unit, doc, conditions, tier, min_prompt_tokens]))
            add("prices", {"id": ident, "offering_id": offering, "category": category,
                           "amount": format(converted.normalize(), "f"), "currency": "USD", "unit": unit,
                           "raw_amount": str(value), "discount": str(discount), "raw_unit": "million_tokens" if per_million else
                           ("token" if unit == "million_tokens" else unit), "conditions": conditions,
                           "tier": tier, "min_prompt_tokens": min_prompt_tokens if min_prompt_tokens is not None else "",
                           "document_id": doc, "observed_at": index["documents"][doc]["retrieved_at"]})
        if isinstance(overrides, list):
            for override in overrides:
                if not isinstance(override, dict):
                    continue
                boundary = override.get("min_prompt_tokens")
                qualifiers = {k: v for k, v in override.items() if k not in TOKEN_CATEGORIES and k not in UNITS and k not in {"overrides"}}
                # Explicit boundary metadata is retained; no inferred effective date/unit.
                rate_fields = {k: v for k, v in override.items() if k in TOKEN_CATEGORIES or k in UNITS}
                rate_fields["discount"] = override.get("discount", str(discount))
                prices(offering, rate_fields, doc, per_million=per_million, tier="override", min_prompt_tokens=boundary,
                       conditions="Source pricing override: " + json.dumps(qualifiers, sort_keys=True))

    def offering(model, key, provider, name, kind, raw, doc, mode="standard", per_million=False, conditions=""):
        ident = uri("offering", key)
        provider_id = org("host:" + provider, provider)
        add("offerings", {"id": ident, "model_id": model, "provider_id": provider_id, "provider_name": provider,
                          "name": name, "kind": kind, "mode": mode, "context_length": raw.get("context_length", ""),
                          "max_output_tokens": raw.get("max_completion_tokens", ""), "status": raw.get("status", ""),
                          "endpoint_tag": raw.get("tag", ""), "quantization": raw.get("quantization", ""),
                          "document_id": doc, "source_url": index["documents"][doc]["url"],
                          "observed_at": index["documents"][doc]["retrieved_at"]})
        prices(ident, raw.get("pricing"), doc, per_million=per_million, conditions=conditions)
        for key, pred in [("context_length", "contextLength"), ("max_completion_tokens", "maxOutputTokens")]:
            if raw.get(key) is not None and raw.get(key) != "":
                observe(ident, pred, raw[key], doc, datatype="integer")
        for parameter in raw.get("supported_parameters") or []:
            capability = uri("capability", parameter)
            add("capabilities", {"id": capability, "name": parameter})
            observe(ident, "supportsCapability", capability, doc, resource=True)
        for key, pred in [("uptime_last_1d", "uptimeLastDay"), ("latency_last_30m", "latencyLast30Minutes"),
                          ("throughput_last_30m", "throughputLast30Minutes")]:
            if isinstance(raw.get(key), (int, float)):
                observe(ident, pred, raw[key], doc, datatype="decimal")
        return ident

    catalog_doc = document(catalog_url, "OpenRouter model catalog")
    router = org("host:OpenRouter", "OpenRouter")
    for source in manifest.get("documents", []):
        document(source["url"], source.get("name", ""), source.get("kind", "document"))
    for raw in catalog["data"]:
        slug = raw["id"]
        prefix = slug.lstrip("~").split("/", 1)[0]
        developer, family = DEVELOPERS.get(prefix, (prefix, prefix))
        # Google Gemma is distinct from Gemini, OpenAI o-series from GPT.
        suffix = slug.split("/", 1)[-1]
        if prefix == "google" and "gemma" in suffix:
            family = "Gemma"
        elif prefix == "openai" and suffix.startswith(("o1", "o3", "o4")):
            family = "OpenAI o-series"
        developer_id = org("developer:" + prefix, developer)
        family_id = uri("model-family", prefix + ":" + family)
        add("families", {"id": family_id, "name": family, "developer_id": developer_id})
        ident = uri("model", "openrouter:" + slug)
        created = raw.get("created")
        try:
            created = datetime.fromtimestamp(created, timezone.utc).isoformat() if created is not None else ""
        except (TypeError, ValueError, OverflowError):
            created = ""
        add("models", {"id": ident, "source_id": slug, "name": raw.get("name", slug),
                       "description": raw.get("description", ""), "family_id": family_id, "family_name": family,
                       "developer_id": developer_id, "developer_name": developer, "catalog_created": created,
                       "canonical_slug": raw.get("canonical_slug", ""), "hugging_face_id": raw.get("hugging_face_id") or "",
                       "document_id": catalog_doc, "knowledge_cutoff": raw.get("knowledge_cutoff") or "",
                       "expiration_date": raw.get("expiration_date") or ""})
        observe(ident, "description", raw.get("description"), catalog_doc)
        repo = raw.get("hugging_face_id")
        if repo and repo in (model_cards or {}):
            from .model_cards import card_url
            url = card_url(repo)
            if url in source_docs:
                card = model_cards[repo]
                doc = document(url, "Publisher model card: " + repo, "model_card")
                metadata = card.get("cardData") or {}
                license_value = metadata.get("license")
                if isinstance(license_value, (str, list)):
                    observe(ident, "license", json.dumps(license_value) if isinstance(license_value, list) else license_value, doc)
                total = (card.get("safetensors") or {}).get("total")
                if isinstance(total, int) and total > 0:
                    observe(ident, "parameterCount", total, doc, datatype="integer")
                observe(ident, "libraryName", card.get("library_name"), doc)
                observe(ident, "pipelineTag", card.get("pipeline_tag"), doc)
                observe(ident, "relatedDocumentation", doc, catalog_doc, resource=True)
        arch = raw.get("architecture") or {}
        for key, predicate in [("input_modalities", "inputModality"), ("output_modalities", "outputModality")]:
            for name in arch.get(key) or []:
                modality = uri("modality", name)
                add("modalities", {"id": modality, "name": name})
                observe(ident, predicate, modality, catalog_doc, resource=True)
        mode = "batch" if ":batch" in slug else ("free" if ":free" in slug else "standard")
        limits = raw.get("top_provider") or {}
        offering(ident, "openrouter:" + slug, "OpenRouter", raw.get("name", slug), "openrouter_catalog",
                 {**limits, "context_length": raw.get("context_length"), "pricing": raw.get("pricing"),
                  "supported_parameters": raw.get("supported_parameters")}, catalog_doc, mode=mode)
        for endpoint in (endpoints.get(slug, {}).get("data") or {}).get("endpoints", []):
            source_url = endpoint_url_for(raw)
            doc = document(source_url, "OpenRouter endpoints: " + slug)
            tag = endpoint.get("tag") or endpoint.get("name") or digest(endpoint)
            configuration = {k: endpoint.get(k) for k in ("name", "quantization", "context_length", "max_prompt_tokens", "max_completion_tokens", "supported_parameters")}
            configuration["supported_parameters"] = sorted(configuration["supported_parameters"] or [])
            endpoint_key = tag + ":" + digest(configuration)
            offering(ident, "openrouter:" + slug + ":" + endpoint_key, endpoint.get("provider_name") or "Unknown provider",
                     endpoint.get("name", tag), "openrouter_endpoint", endpoint, doc, mode=mode)
        # Keep embedded benchmark attribution: collected through OpenRouter, not direct AA API.
        for owner, values in (raw.get("benchmarks") or {}).items():
            if not isinstance(values, dict):
                continue
            for metric, value in values.items():
                score = number(value)
                if score is None:
                    continue
                bench_id = uri("benchmark", owner + ":" + metric)
                add("benchmarks", {"id": bench_id, "name": metric, "evaluator": owner,
                                   "unit": "index_points", "version": "not supplied by catalog"})
                evaluation = uri("evaluation", digest([ident, bench_id, catalog_doc, str(score)]))
                add("evaluations", {"id": evaluation, "model_id": ident, "benchmark_id": bench_id,
                                    "score": str(score), "unit": "index_points", "config": "not supplied by catalog",
                                    "document_id": catalog_doc, "source_url": catalog_url, "evaluated_at": "",
                                    "attribution": owner + " via OpenRouter"})
        # Attach developer documentation as relevant documentation, not as field-level proof.
        for source in manifest.get("documents", []):
            if source.get("developer") == prefix and source.get("kind") == "official":
                observe(ident, "relatedDocumentation", document(source["url"]), catalog_doc, resource=True)

    for fact in official_facts or []:
        # Curated fact must refer to an actually fetched source snapshot with matching evidence.
        source = source_docs.get(fact["source_url"])
        if not source or (fact.get("source_sha256") and fact["source_sha256"] != source.get("sha256")):
            add("unmatched", {"id": digest(fact), "kind": "official_fact", "name": fact.get("name", ""),
                              "reason": "source snapshot absent or checksum changed", "source_url": fact["source_url"]})
            continue
        doc = document(fact["source_url"], kind="official")
        slug = fact["model_id"]
        ident = uri("model", "openrouter:" + slug) if slug in {m["source_id"] for m in index["models"].values()} else uri("model", "official:" + slug)
        if ident not in index["models"]:
            prefix = slug.split("/", 1)[0]
            developer, family = DEVELOPERS.get(prefix, (prefix, prefix))
            dev_id = org("developer:" + prefix, developer)
            fam_id = uri("model-family", prefix + ":" + family)
            add("families", {"id": fam_id, "name": family, "developer_id": dev_id})
            add("models", {"id": ident, "source_id": slug, "name": fact["name"], "family_id": fam_id,
                           "family_name": family, "developer_id": dev_id, "developer_name": developer,
                           "document_id": doc, "description": "", "catalog_created": ""})
        for pred, value in fact.get("facts", {}).items():
            observe(ident, pred, value, doc, datatype="integer" if isinstance(value, int) else "string")
        if fact.get("pricing"):
            offering(ident, "direct:" + slug + ":" + fact.get("tier", "standard"), fact["provider"], fact["name"], "direct",
                     {"pricing": fact["pricing"], "context_length": fact.get("facts", {}).get("contextLength", "")},
                     doc, mode=fact.get("tier", "standard"), per_million=True, conditions=fact.get("conditions", ""))

    for review in reviews or []:
        if review.get("source_url") not in source_docs:
            continue
        doc = document(review["source_url"], kind="review")
        for slug in review.get("model_ids", []):
            match = next((m for m in index["models"].values() if m["source_id"] == slug), None)
            if not match:
                add("unmatched", {"id": digest([review, slug]), "kind": "review", "name": review["title"],
                                  "reason": "explicit model ID absent from catalog", "source_url": review["source_url"]})
                continue
            add("reviews", {"id": uri("review", digest([review["source_url"], slug])), "model_id": match["id"],
                            "name": review["title"], "author": review["author"], "date": review.get("date", ""),
                            "summary": review.get("summary", ""), "document_id": doc, "source_url": review["source_url"]})
    for key in TABLES:
        tables[key] = sorted(index[key].values(), key=lambda row: row["id"])
    return tables


def endpoint_url_for(model):
    from .collect import endpoint_url
    return endpoint_url(model)


def main():
    manifest = read_json(BRONZE / "manifest.json")
    tables = normalize(read_json(BRONZE / manifest.get("catalog_file", "openrouter_models.json")),
                       read_json(BRONZE / manifest.get("endpoints_file", "openrouter_endpoints.json")),
                       manifest, read_json(RES / "official-model-facts.json"), read_json(RES / "reviews.json"),
                       read_json(BRONZE / manifest["model_cards_file"]) if manifest.get("model_cards_file") else {})
    from .benchmarks import add_aider
    add_aider(tables, manifest)
    write_tables(tables)
    report = {"tables": {k: len(v) for k, v in tables.items()},
              "models_by_developer": dict(Counter(m["developer_name"] for m in tables["models"])),
              "offerings_by_kind": dict(Counter(o["kind"] for o in tables["offerings"])),
              "retrieved_at": manifest["retrieved_at"], "warnings": manifest["warnings"]}
    write_json(RES / "coverage.json", report)
    print(json.dumps(report["tables"], indent=2))


if __name__ == "__main__":
    main()
