# Competency questions: từ kịch bản đến truy vấn

Các câu hỏi bên dưới thuộc nhánh nghiên cứu. Các câu hỏi model/provider/giá/
benchmark mới được mô tả ở [MODEL_CATALOG.md](MODEL_CATALOG.md) và hiện thực
trong `queries/models/`.

Chạy mọi truy vấn trên ontology + dữ liệu + links + metadata trong default
graph. `validate.py` lưu số dòng và first row vào validation-report.json.
Mẫu OpenAlex thay đổi theo thời gian, nên không đóng đinh tên bài hay citation
count cho mọi lần lấy dữ liệu.

| CQ | Câu hỏi tự nhiên | SPARQL trong queries/ | Expected answer trên fixture synthetic |
|---|---|---|---|
| 1 | Bài nào nhiều trích dẫn nhất; năm nào? | cq01_top_papers.rq | Hai bài W1/W2, năm 2024, citations 5 |
| 2 | Ai viết bài, position/affiliation của từng người trong bài đó? | cq02_authorship_affiliations.rq | W1: A1-I1; W2: A1-I2; cùng A1 không làm mất bối cảnh |
| 3 | Tổ chức nào có bao nhiêu bài trong mẫu? | cq03_institution_productivity.rq | I1 và I2, mỗi tổ chức một bài |
| 4 | Topic thuộc subfield/field/domain nào? | cq04_topic_hierarchy.rq | T1 → Artificial Intelligence → Computer Science → Physical Sciences; 2 bài |
| 5 | Bài được công bố ở sources nào, publisher nào? | cq05_sources_publishers.rq | S1 Example Journal → Example Publisher, 2 bài |
| 6 | Theo năm, bao nhiêu bài open access? | cq06_open_access_by_year.rq | Một dòng: 2024, true, 2 bài |
| 7 | Entity nào link với Wikidata/DBpedia? | cq07_external_links.rq | 0 dòng trong fixture; graph thật phải có links đã xác minh |
| 8 | Bài nào tham khảo bài nào; target có trong mẫu không? | cq08_references.rq | W1 tham khảo W2, có local title Example paper 2 |
| 9 | Bài nào có affiliation từ ít nhất hai tổ chức? | cq09_collaboration.rq | 0 dòng; hai tổ chức của A1 ở hai bài không phải hợp tác trong cùng bài |
| 10 | OpenAlex/DOI/ORCID/ROR nào nhận diện các entity? | cq10_identifiers_provenance.rq | Hai dòng paper-context, OpenAlex W1/W2, A1 ORCID; ROR I1/I2, DOI unbound |

Trên snapshot thật: CQ1 tối đa 20 bài, CQ2 tối đa 100 dòng author-affiliation,
CQ3 tối đa 20 institutions, CQ4 tối đa 20 topics, CQ8 tối đa 50 references,
CQ9 tối đa 20 bài, CQ10 tối đa 50 dòng. Những `LIMIT` này phục vụ đọc kết quả,
không giảm số entities đã thu thập.

**Kiểm tra logic bổ sung:** `inference_authored_paper.rq` trả 0 dòng trên
asserted fixture. Sau OWL RL nó phải trả hai dòng Authorship → Paper, do
inverseOf. Không có Person nào suy ra thành Authorship hay Institution.

**Cách kiểm tra:** unittest dựng fixture trong bộ nhớ; kiểm tra các kết quả
kỳ vọng và typed triples; validate chạy đủ CQs trên snapshot thật. Không
đánh giá “query chạy thành công” là đủ để chứng minh dữ liệu đúng toàn bộ;
cần xem outputs và bằng chứng nguồn khi mở rộng dữ liệu.
