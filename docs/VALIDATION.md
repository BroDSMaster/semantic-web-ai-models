# Kết quả kiểm tra snapshot

Đã kiểm tra ngày 2026-10-04 UTC, trước khi người dùng yêu cầu tự chạy các
lệnh. Các số dưới thuộc snapshot đi kèm; thu thập lại có thể thay đổi chúng.

## Dữ liệu và RDF

| Class | Instances |
|---|---:|
| ResearchPaper | 200 |
| Person | 1.807 |
| ResearchInstitution | 307 |
| PublicationSource | 65 |
| Publisher | 19 |
| ResearchTopic | 101 |
| ResearchSubfield | 33 |
| ResearchField | 11 |
| ResearchDomain | 4 |
| Authorship | 2.128 |

Chỉ lấy article/conference-paper/preprint/review, loại paratext. JSON gốc và
URL/thời điểm thu thập được giữ trong bronze.

- Instance graph: **49.459 triples**.
- Ontology: **184 triples**; metadata: **15 triples**.
- Identity links: **2.593 triples**.
- Tổng graph: **52.251 triples**.
- OWL RL closure: **158.572 triples**, không phát hiện lỗi theo rule checks
  và validator của project. Không coi đây là chứng minh toàn bộ OWL DL.

## Linking và giới hạn nguồn

| Method | Links | Bằng chứng |
|---|---:|---|
| exact_openalex_id | 2.547 | IDs trong snapshot OpenAlex |
| openalex_declared_wikidata_id | 25 | QIDs trong OpenAlex full records |
| exact_ror_P6782 | 10 | ROR khớp chính xác trong Wikidata SPARQL |
| dbpedia_declared_sameAs_wikidata | 11 | DBpedia trả sameAs đúng QID |

35 QID được tra DBpedia: 11 có mapping xác nhận; 21 lookup trả HTTP 503;
3 lookup khác hoàn tất nhưng không có resource hợp lệ được chấp nhận.
Lỗi mạng không có nghĩa “DBpedia không có entity”. Không đoán URI để bù
links; bản offline chỉ dùng phản hồi đã ghi.

Xem [linking report](../res/linking-report.json),
[evidence CSV](../res/entity_links.csv),
[lookup snapshots](../src/data/bronze/external_lookups.json).

## Kiểm thử và reproducibility

**10 tests pass:** duplicate works; affiliation theo paper; thiếu author ID;
typed literals; loại proceedings collections; exact identity matching;
JSON/SPARQL media types; phân trang 150 bài không lặp; round-trip và expected
answers cho 10 CQs trên fixture synthetic.

Kiểm tra dữ liệu thật đã xác nhận bronze tạo cùng silver; silver tạo cùng
graph với cả Turtle/RDF/XML; ontology serializations isomorphic; linker
offline tạo cùng graph/evidence, giữ nguyên thời điểm kiểm tra nguồn.
Report: [reproducibility-report.json](../res/reproducibility-report.json).

## Fuseki thật

Đã nạp bốn files vào default graph của Apache Jena Fuseki 6.2.0/Java 21,
cấu hình TDB2 của project. Truy vấn qua HTTP POST và so toàn bộ values với
RDFLib local, không chỉ row counts.

| Query | Dòng local / Fuseki | Kết quả |
|---|---:|---|
| count_classes | 10 / 10 | Khớp |
| CQ1 | 20 / 20 | Khớp |
| CQ2 | 100 / 100 | Khớp |
| CQ3 | 20 / 20 | Khớp |
| CQ4 | 20 / 20 | Khớp |
| CQ5 | 65 / 65 | Khớp |
| CQ6 | 19 / 19 | Khớp |
| CQ7 | 46 / 46 | Khớp |
| CQ8 | 50 / 50 | Khớp |
| CQ9 | 20 / 20 | Khớp |
| CQ10 | 50 / 50 | Khớp |

Với GROUP_CONCAT institutions, check bỏ khác biệt thứ tự chuỗi gộp vì SPARQL
không quy định thứ tự đó. Triple count local/Fuseki cùng 52.251.
Report: [fuseki-validation.json](../res/fuseki-validation.json).
CLI ask.py --endpoint cũng đã chạy thật.

Fuseki hiện được dừng theo yêu cầu người dùng. Để tự kiểm tra:

```bash
# Terminal 1, từ aimodels/
bash scripts/start_fuseki.sh
# Terminal 2, từ aimodels/, sau khi activate .venv
bash scripts/load_fuseki.sh
python tests/check_fuseki.py
```

TDB2 cấu hình lưu tại run/tdb2. Có thể tự kiểm tra persistence bằng cách
dừng/khởi động lại server và chạy count_classes, không load lại dữ liệu.
Phiên kiểm tra chưa xác nhận lại query sau restart.

## Giới hạn của kết luận

Kiểm tra xác nhận cấu trúc, mappings, reproducibility, một tập OWL RL
semantics và CQs. Không chứng minh mọi affiliation, topic/citation count hay
entity resolution của nguồn đều đúng ngoài đời. Namespace example.org là
minh họa; chưa công bố LOD public với URI dereference/download URLs.
