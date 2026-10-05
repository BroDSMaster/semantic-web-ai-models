# Kiểm chứng AI model catalog

Đã kiểm chứng local trên snapshot thu thập ngày 2026-10-05. Fuseki chưa được khởi động hoặc nạp dữ liệu bởi agent.

## Kết quả

- 27 unit/regression tests đạt (gồm 10 tests nhánh research hiện có).
- Cả 13 file SPARQL thực thi thành công trên graph đầy đủ.
- Graph kết hợp có 353,882 triples; CSV/RDF entity counts khớp, không có dangling price/evaluation hoặc ID trùng.
- 576 source snapshots vượt kiểm tra SHA-256 của response bytes lưu tại bronze.
- OWL RL kiểm tra trên fixture đại diện của ontology; không chạy closure toàn catalog.
- CLI ask.py đã chạy thành công với query Opus và lưu 336 dòng kết quả.

| Query | Số dòng | Thời gian query (giây) |
|---|---:|---:|
| `benchmarks.rq` | 471 | 0.27 |
| `cheap_tool_models.rq` | 50 | 0.813 |
| `claude_models.rq` | 37 | 0.021 |
| `conflicting_observations.rq` | 0 | 0.182 |
| `coverage.rq` | 58 | 0.034 |
| `direct_vs_router.rq` | 1257 | 3.038 |
| `external_links.rq` | 5 | 0.007 |
| `model_details.rq` | 116 | 0.054 |
| `official_sources.rq` | 399 | 1.151 |
| `open_weight_specs.rq` | 391 | 1.974 |
| `opus_providers_prices.rq` | 336 | 4.772 |
| `reviews.rq` | 4 | 0.012 |
| `vision_models.rq` | 295 | 0.04 |

Thời gian trên không bao gồm đọc/parse RDF từ đĩa. Query conflicts trả 0 là kết quả hợp lệ: không thấy model context/output/cutoff có nhiều giá trị trong tập quan sát đang xét. Không chứng minh mọi nguồn luôn đồng thuận.

## Bằng chứng và chạy lại

- [Báo cáo máy đọc được](../res/model-validation-report.json)
- [Coverage và cảnh báo collection](../res/model-coverage.json)
- [Toàn bộ kết quả CLI Opus](../res/opus-provider-prices.csv)
- [Mẫu giá Opus 4.6](../res/opus-4.6-price-sample.json)
- [Hướng dẫn chạy và nạp Fuseki](MODEL_CATALOG.md)

```bash
cd /home/puda14/Desktop/Project/semantic-web/aimodels
.venv/bin/python -m unittest discover -s tests
PYTHONPATH=src .venv/bin/python -m model_catalog.validate
.venv/bin/python src/ask.py queries/models/opus_providers_prices.rq --dataset models
```

## Phạm vi và giới hạn

Đây là kiểm chứng local, chưa xác minh query qua Fuseki server của người dùng. Ba Hugging Face responses không khớp repository ID đã bị bỏ qua; một ứng viên identity Wikidata chưa xác nhận được official website nên không xuất sameAs. Những cảnh báo này nằm trong coverage/link report, không bị coi là dữ liệu đã xác minh.

Benchmark/review chỉ có cho một phần model. Giá trực tiếp có parser nhận dạng cho OpenAI, Anthropic, MiniMax và Z.AI; các hãng khác có catalog/router prices và tài liệu liên quan. Các listing alias/free/batch không phải những bộ weights độc lập. Namespace example.org cần được thay và xuất bản để công bố LOD truy cập công khai.
