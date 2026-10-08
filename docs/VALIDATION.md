# Kiểm chứng AI model catalog

Snapshot catalog ngày 2026-10-05 được kiểm chứng local lại ngày 2026-10-08 sau khi thêm liên kết tổ chức. JSON Wikidata/DBpedia/OpenAlex mới được truy xuất ngày 2026-10-08. Fuseki không được khởi động hoặc nạp dữ liệu trong lần này.

## Kết quả

- 31 unit/regression tests riêng của aimodels đạt; gồm kiểm tra OpenAlex ID/name/type/homepage/ROR/QID, domain không chứa dữ liệu nhận xét chủ quan, checksum bị sửa và sai repository HF.
- Cả 15 file SPARQL thực thi thành công trên graph đầy đủ.
- Graph kết hợp có 355.218 triples; CSV/RDF entity counts khớp, không có dangling price/evaluation hoặc ID trùng.
- 573 source snapshots vượt kiểm tra SHA-256 của response bytes lưu tại bronze.
- 9 snapshots OpenAlex được phát lại kiểm tra riêng. 50 snapshots Wikidata/DBpedia được kiểm tra checksum và phát lại mapping. RDF có 77 sameAs cho tổ chức/dịch vụ và 102 quan hệ tới 92 repository HF; không có sameAs cấp model.
- OWL RL kiểm tra trên fixture đại diện của ontology; không chạy closure toàn catalog.
- CLI ask.py đã chạy thành công với query Opus và lưu 336 dòng kết quả.

| Query | Số dòng | Thời gian query (giây) |
|---|---:|---:|
| `benchmarks.rq` | 471 | 0.22 |
| `cheap_tool_models.rq` | 50 | 0.794 |
| `claude_models.rq` | 37 | 0.022 |
| `conflicting_observations.rq` | 0 | 0.213 |
| `coverage.rq` | 58 | 0.046 |
| `direct_vs_router.rq` | 1257 | 3.525 |
| `external_links.rq` | 77 | 0.016 |
| `linked_providers.rq` | 36 | 0.191 |
| `model_details.rq` | 116 | 0.051 |
| `model_repositories.rq` | 102 | 0.154 |
| `official_sources.rq` | 399 | 1.336 |
| `open_weight_specs.rq` | 391 | 2.161 |
| `openalex_organizations.rq` | 9 | 0.148 |
| `opus_providers_prices.rq` | 336 | 4.786 |
| `vision_models.rq` | 295 | 0.039 |

Các thời gian trong bảng lấy từ lần kiểm tra ngày 08/10 và không bao gồm đọc/parse RDF từ đĩa. Query conflicts trả 0 là kết quả hợp lệ: không thấy model context/output/cutoff có nhiều giá trị trong tập quan sát đang xét. Không chứng minh mọi nguồn luôn đồng thuận.

## Bằng chứng và chạy lại

- [Báo cáo máy đọc được](../res/validation-report.json)
- [Coverage và cảnh báo collection](../res/coverage.json)
- [Toàn bộ kết quả CLI Opus](../res/opus-provider-prices.csv)
- [Mẫu giá Opus 4.6](../res/opus-4.6-price-sample.json)
- [Hướng dẫn chạy và nạp Fuseki](PIPELINE.md)

```bash
cd /home/puda14/Desktop/Project/semantic-web/aimodels
.venv/bin/python -m unittest discover -s tests
PYTHONPATH=src .venv/bin/python -m model_catalog.validate
.venv/bin/python src/ask.py queries/opus_providers_prices.rq
```

## Phạm vi và giới hạn

Đây là kiểm chứng local, chưa xác minh query qua Fuseki server của người dùng. Ba Hugging Face responses không khớp repository ID đã bị bỏ qua; các tên chưa có mapping identity đủ bằng chứng không được tự ghép theo tên. Những cảnh báo này nằm trong coverage/link report, không bị coi là dữ liệu đã xác minh.

Benchmark chỉ có cho một phần model. Giá trực tiếp có parser nhận dạng cho OpenAI, Anthropic, MiniMax và Z.AI; các hãng khác có catalog/router prices và tài liệu liên quan. Các listing alias/free/batch không phải những bộ weights độc lập. Namespace đã chuyển sang GitHub Pages; URI truy cập công khai sau khi workflow Pages được deploy.
