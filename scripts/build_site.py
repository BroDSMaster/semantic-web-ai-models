#!/usr/bin/env python3
"""Build the static GitHub Pages interface and public RDF distribution."""
import argparse
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from model_catalog.common import PUBLIC_SITE, RES, read_tables
from model_catalog.transform import load_model_graph


def number(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def build_catalog(tables):
    families = {r["id"]: r["name"] for r in tables["families"]}
    organizations = {r["id"]: r["name"] for r in tables["organizations"]}
    benchmarks = {r["id"]: r["name"] for r in tables["benchmarks"]}
    offerings, prices, evaluations, observations, links, offering_ids = (defaultdict(list) for _ in range(6))
    for r in tables["prices"]:
        prices[r["offering_id"]].append({"category": r["category"], "amount": number(r["amount"]), "currency": r["currency"], "unit": r["unit"], "tier": r["tier"], "conditions": r["conditions"]})
    for r in tables["offerings"]:
        offerings[r["model_id"]].append({"id": r["id"], "provider": r["provider_name"], "kind": r["kind"], "mode": r["mode"], "context_length": number(r["context_length"]), "max_output_tokens": number(r["max_output_tokens"]), "quantization": r["quantization"], "source_url": r["source_url"], "prices": prices[r["id"]]})
        offering_ids[r["model_id"]].append(r["id"])
    for r in tables["evaluations"]:
        evaluations[r["model_id"]].append({"benchmark": benchmarks.get(r["benchmark_id"], r["benchmark_id"]), "score": number(r["score"]), "unit": r["unit"], "attribution": r["attribution"], "source_url": r["source_url"]})
    wanted = {"description", "inputModality", "outputModality", "supportsCapability"}
    for r in tables["observations"]:
        if r["predicate"] in wanted:
            observations[r["subject_id"]].append((r["predicate"], r["value"]))
    for r in tables["external_links"]:
        links[r["subject"]].append({"target": r["target"], "reason": r["reason"], "evidence": r["source_url"]})
    models = []
    for r in tables["models"]:
        facts = defaultdict(list)
        for subject in [r["id"], *offering_ids[r["id"]]]:
            for predicate, value in observations[subject]:
                facts[predicate].append(value)
        models.append({"id": r["id"], "source_id": r["source_id"], "name": r["name"], "developer": r.get("developer_name") or organizations.get(r["developer_id"], ""), "family": r.get("family_name") or families.get(r["family_id"], ""), "catalog_created": r["catalog_created"], "knowledge_cutoff": r["knowledge_cutoff"], "hugging_face_id": r["hugging_face_id"], "description": (facts["description"] or [r.get("description", "")])[0], "input_modalities": sorted(set(facts["inputModality"])), "output_modalities": sorted(set(facts["outputModality"])), "capabilities": sorted({v.rsplit("/", 1)[-1].rsplit("#", 1)[-1] for v in facts["supportsCapability"]}), "offerings": offerings[r["id"]], "evaluations": evaluations[r["id"]]})
    model_counts = Counter(r["developer_id"] for r in tables["models"])
    host_counts = Counter(r["provider_id"] for r in tables["offerings"])
    orgs = [{"id": r["id"], "name": r["name"], "models": model_counts[r["id"]], "offerings": host_counts[r["id"]], "external_links": links[r["id"]]} for r in tables["organizations"]]
    return {"site": PUBLIC_SITE, "stats": {"models": len(tables["models"]), "offerings": len(tables["offerings"]), "prices": len(tables["prices"]), "evaluations": len(tables["evaluations"]), "organizations": len(tables["organizations"]), "external_links": len(tables["external_links"]), "triples": len(load_model_graph())}, "models": sorted(models, key=lambda r: r["name"].lower()), "organizations": sorted(orgs, key=lambda r: r["name"].lower())}


def page(title, section, content, depth=1):
    root = "../" if depth else "./"
    items = [("home", "", "Tổng quan"), ("models", "models/", "Models"), ("organizations", "organizations/", "Tổ chức"), ("ontology", "ontology/", "Ontology"), ("sparql", "sparql/", "SPARQL"), ("dataset", "dataset/", "Dataset")]
    nav = "".join(f'<a href="{root}{path}" class="{"active" if key == section else ""}">{label}</a>' for key, path, label in items)
    return f'''<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="AI Models Linked Open Data catalog"><title>{title} · AI Models LOD</title><link rel="stylesheet" href="{root}assets/styles.css"></head><body data-section="{section}" data-root="{root}"><header><a class="brand" href="{root}"><span>AI</span> Models LOD</a><nav>{nav}</nav></header><main>{content}</main><footer>AI Models Linked Open Data · dữ liệu có provenance · <a href="{root}dataset/">license và tải xuống</a></footer><script src="{root}assets/app.js"></script></body></html>'''


def build(output):
    output = Path(output)
    (output / "assets").mkdir(parents=True, exist_ok=True)
    (output / "data").mkdir(parents=True, exist_ok=True)
    tables = read_tables()
    catalog = build_catalog(tables)
    (output / "data/catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    load_model_graph().serialize(output / "data/aimodels.ttl", format="turtle")
    for source, target in [(RES / "ontology.ttl", "ontology.ttl"), (RES / "dataset-metadata.ttl", "dataset-metadata.ttl"), (RES / "linked_output.nt", "linked-output.nt")]:
        shutil.copyfile(source, output / "data" / target)
    for source, target in [(ROOT / "LICENSE", "LICENSE.txt"), (ROOT / "DATA_LICENSE.md", "DATA_LICENSE.txt")]:
        shutil.copyfile(source, output / target)
    shutil.copyfile(ROOT / "web/styles.css", output / "assets/styles.css")
    shutil.copyfile(ROOT / "web/app.js", output / "assets/app.js")
    (output / ".nojekyll").touch()
    home = '''<section class="hero"><p class="eyebrow">Linked Open Data capstone</p><h1>Tra cứu model AI, API, giá và nguồn chứng minh</h1><p>Project gom dữ liệu từ OpenRouter và nguồn chính thức, chuẩn hóa thành RDF, nối tổ chức với Wikidata, DBpedia và OpenAlex, rồi xuất bản để con người và máy đều đọc được.</p><div class="actions"><a class="button" href="models/">Khám phá model</a><a class="button secondary" href="data/aimodels.ttl">Tải RDF Turtle</a></div></section><section><h2>Tình trạng dữ liệu</h2><div id="stats" class="stats loading">Đang đọc catalog…</div></section><section class="flow"><h2>Luồng dữ liệu</h2><div class="flow-grid"><article><b>1 · Bronze</b><p>JSON gốc và URL truy xuất.</p></article><article><b>2 · Silver</b><p>CSV chuẩn hóa theo entity.</p></article><article><b>3 · Gold</b><p>RDF dùng ontology và typed literal.</p></article><article><b>4 · Linked</b><p>Liên kết tổ chức đã xác minh.</p></article><article><b>5 · Publish</b><p>Website và Turtle URI công khai.</p></article></div></section>'''
    models = '''<section class="page-head"><p class="eyebrow">Catalog</p><h1>Model và API offering</h1><p>Mỗi model có thể có nhiều nơi cung cấp API; mỗi offering có giá và thông số riêng.</p></section><div class="toolbar"><input id="model-search" type="search" placeholder="Tìm GPT, Claude, Gemini, Qwen…"><select id="developer-filter"><option value="">Mọi nhà phát triển</option></select></div><p id="model-count" class="muted"></p><div class="split"><div id="model-list" class="cards loading">Đang tải…</div><aside id="model-detail" class="detail"><p>Chọn một model để xem chi tiết.</p></aside></div>'''
    orgs = '''<section class="page-head"><p class="eyebrow">5-star links</p><h1>Tổ chức và liên kết ngoài</h1><p><code>owl:sameAs</code> chỉ được tạo khi danh tính tổ chức được kiểm tra bằng website chính thức, QID hoặc ROR.</p></section><input id="org-search" type="search" placeholder="Tìm Anthropic, OpenAI, Google…"><div id="org-list" class="cards loading">Đang tải…</div>'''
    ontology = '''<section class="page-head"><p class="eyebrow">Schema</p><h1>Ontology mô tả điều gì?</h1><p>Ontology tách model, nơi cung cấp API, giá, đánh giá và nguồn chứng minh thành các thực thể có quan hệ rõ ràng.</p></section><div class="ontology-grid">''' + "".join(f"<article><h3>{name}</h3><p>{desc}</p></article>" for name, desc in [("AIModel", "Một model logic."), ("ModelFamily", "Dòng model như Claude hoặc GPT."), ("Organization", "Nhà phát triển hoặc nhà cung cấp."), ("ModelOffering", "Một cách truy cập model qua provider."), ("PriceSpecification", "Giá theo prompt, completion hay request."), ("Benchmark", "Bài hoặc chỉ số đánh giá."), ("Evaluation", "Kết quả model trên benchmark."), ("Capability", "Khả năng như tools hoặc vision."), ("Modality", "Kiểu vào/ra: text, image, audio."), ("SourceDocument", "Tài liệu nguồn và thời điểm lấy."), ("FactObservation", "Một phát biểu gắn với provenance."), ("ExternalLink", "Bằng chứng của liên kết ngoài.")]) + '''</div><div class="relation"><code>Organization → developedBy ← AIModel → offersModel ← ModelOffering → hasPrice → PriceSpecification</code></div><p><a class="button" href="../data/ontology.ttl">Mở ontology.ttl</a></p>'''
    sparql = '''<section class="page-head"><p class="eyebrow">Query</p><h1>SPARQL endpoint và terminal</h1><p>GitHub Pages phục vụ file RDF tĩnh. Để chạy SPARQL, nạp các file vào Apache Jena Fuseki hoặc dùng CLI offline.</p></section><div class="notice"><b>Fuseki local:</b> <code>http://localhost:3030/aimodels/sparql</code></div><h2>Ví dụ: tìm model và nhà phát triển</h2><pre><code>PREFIX ex: &lt;https://brodsmaster.github.io/semantic-web-ai-models/data/aimodels.ttl#&gt;
PREFIX rdfs: &lt;http://www.w3.org/2000/01/rdf-schema#&gt;
SELECT ?model ?name ?developerName WHERE {
  ?model a ex:AIModel ; rdfs:label ?name ; ex:developedBy ?developer .
  ?developer rdfs:label ?developerName .
  FILTER(CONTAINS(LCASE(STR(?name)), "claude"))
} ORDER BY ?name</code></pre><h2>Chạy offline</h2><pre><code>PYTHONPATH=src .venv/bin/python src/ask.py --file queries/model_details.rq</code></pre>'''
    dataset = '''<section class="page-head"><p class="eyebrow">Download</p><h1>Dữ liệu công khai</h1><p>Bản Turtle kết hợp ontology, catalog, external links và metadata. URI có fragment trỏ trực tiếp vào tài liệu này.</p></section><div class="downloads"><a href="../data/aimodels.ttl"><b>aimodels.ttl</b><span>Knowledge graph đầy đủ</span></a><a href="../data/ontology.ttl"><b>ontology.ttl</b><span>Classes và properties</span></a><a href="../data/dataset-metadata.ttl"><b>dataset-metadata.ttl</b><span>DCAT metadata</span></a><a href="../data/catalog.json"><b>catalog.json</b><span>Dữ liệu cho giao diện</span></a></div><h2>License</h2><p>Mã nguồn dùng MIT. Ontology và phần dữ liệu do project tạo dùng CC BY 4.0 trong phạm vi quyền của tác giả. Nội dung bên thứ ba vẫn theo điều khoản của từng nguồn.</p><p><a href="../LICENSE.txt">MIT License</a> · <a href="../DATA_LICENSE.txt">Data license</a></p>'''
    pages = {"index.html": page("Tổng quan", "home", home, 0), "models/index.html": page("Models", "models", models), "organizations/index.html": page("Tổ chức", "organizations", orgs), "ontology/index.html": page("Ontology", "ontology", ontology), "sparql/index.html": page("SPARQL", "sparql", sparql), "dataset/index.html": page("Dataset", "dataset", dataset)}
    for relative, html in pages.items():
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    return catalog


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "site")
    args = parser.parse_args()
    result = build(args.output)
    print(f"Built {args.output} with {result['stats']['models']} models")
