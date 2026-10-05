"""Collect public repository metadata from publisher namespaces explicitly listed here."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

from .common import BRONZE, atomic_write, digest, fetch, now, read_json, write_json

PUBLISHERS = {"Qwen", "meta-llama", "mistralai", "zai-org", "MiniMaxAI", "deepseek-ai", "google", "openai"}


def card_url(repo):
    return "https://huggingface.co/api/models/" + quote(repo, safe="/")


def collect_cards(offline=False):
    manifest = read_json(BRONZE / "manifest.json")
    if offline:
        if not manifest.get("model_cards_file"):
            raise FileNotFoundError("No model card snapshot; first collect online")
        return read_json(BRONZE / manifest["model_cards_file"])
    catalog = read_json(BRONZE / manifest.get("catalog_file", "openrouter_models.json"))
    repos = sorted({m["hugging_face_id"] for m in catalog["data"] if m.get("hugging_face_id")
                    and m["hugging_face_id"].split("/", 1)[0] in PUBLISHERS})
    cards, documents, warnings = {}, [], []

    def one(repo):
        url = card_url(repo)
        content = fetch(url)
        payload = json.loads(content)
        if not isinstance(payload, dict) or payload.get("id") != repo:
            raise ValueError("Repository identity/schema mismatch")
        filename = "documents/hf-" + digest(content) + ".json"
        atomic_write(BRONZE / filename, content)
        return repo, payload, {"id": "hf:" + repo, "url": url, "name": "Publisher model card: " + repo,
                               "kind": "model_card", "file": filename, "sha256": digest(content), "retrieved_at": now()}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(one, repo): repo for repo in repos}
        for future in as_completed(futures):
            try:
                repo, payload, document = future.result()
                cards[repo] = payload
                documents.append(document)
            except (RuntimeError, ValueError) as exc:
                warnings.append({"model_card": futures[future], "error": str(exc)})
    if not cards:
        raise RuntimeError("No publisher cards collected; current manifest/cards preserved")
    filename = "snapshots/model-cards-" + digest(cards) + ".json"
    write_json(BRONZE / filename, cards)
    manifest["model_cards_file"] = filename
    manifest["publisher_cards"] = len(cards)
    manifest["documents"] = [d for d in manifest["documents"] if not d.get("id", "").startswith("hf:")] + documents
    manifest["warnings"].extend(warnings)
    write_json(BRONZE / "manifest.json", manifest)
    print(f"Publisher cards: {len(cards)}/{len(repos)}; warnings: {len(warnings)}", flush=True)
    return cards


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    collect_cards(parser.parse_args().offline)
