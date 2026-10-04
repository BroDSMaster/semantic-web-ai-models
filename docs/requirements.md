# Phạm vi và yêu cầu ontology

Phương pháp: [ONTOLOGY_ENGINEERING_SKILL.md](../../ONTOLOGY_ENGINEERING_SKILL.md).
Miền được chọn là **nghiên cứu AI**, mẫu ban đầu gồm bài về large language
models có primary field Computer Science theo OpenAlex; chỉ lấy individual
article/conference-paper/preprint/review, loại paratext và collections. Tên thư mục `aimodels`
được giữ theo yêu cầu; ontology hiện mô tả nghiên cứu, không phải catalog sản
phẩm GPT/Claude/Qwen.

**Người dùng:** sinh viên làm capstone, giảng viên đánh giá, người tìm tài liệu
AI và nhóm nghiên cứu muốn xem tác giả/tổ chức/chủ đề trong mẫu.

**Trong phạm vi:** metadata bài báo/preprint, người viết, affiliation theo bài,
nguồn xuất bản, publisher, phân loại bốn cấp OpenAlex, danh sách tham khảo,
định danh ngoài và provenance của việc thu thập/liên kết.

**Ngoài phạm vi:** toàn văn, mô hình thương mại, giá API, benchmark chất lượng
LLM, trạng thái việc làm hiện tại, toàn bộ mạng trích dẫn thế giới. Bài được
tham khảo ngoài mẫu giữ URI OpenAlex; không tạo bản ghi đầy đủ giả.

## Kịch bản → yêu cầu

1. Sinh viên tìm bài có nhiều trích dẫn về LLM, xem tác giả và nguồn xuất bản.
   Cần ResearchPaper, Person, Authorship, PublicationSource và thuộc tính năm,
   citation count, DOI (CQ1, CQ2, CQ5, CQ10).
2. Nhóm nghiên cứu tìm tổ chức có nhiều bài và hợp tác liên tổ chức.
   Affiliation phải gắn với từng Authorship, không gắn toàn cục với Person
   (CQ3, CQ9). Số lượng chỉ tính trên mẫu, không được trình bày là xếp hạng thế giới.
3. Giảng viên kiểm tra phân loại, open access, trích dẫn và liên kết LOD.
   Cần bốn cấp classification, URI định danh ổn định, bản ghi bằng chứng liên
   kết, truy vấn local/Fuseki và kiểm tra suy luận (CQ4, CQ6, CQ7, CQ8).

## Yêu cầu phi chức năng và chấp nhận

- URI lấy từ định danh OpenAlex, không dùng tên hoặc số thứ tự dòng CSV.
- Bronze lưu JSON gốc; silver không trùng entity; gold parse được bằng RDFLib
  và Apache Jena. Chạy lại offline được từ snapshot kèm theo.
- Thiếu DOI/ORCID/affiliation được phép; không điền dữ liệu giả.
- Đối chiếu `owl:sameAs` bằng định danh hoặc sameAs của nguồn; tên tương tự
  chỉ là gợi ý, không đủ để xác lập danh tính.
- Có 10 competency queries, kiểm thử fixture và kiểm tra OWL RL.
- Cả terminal và endpoint phải chạy cùng SPARQL trên cùng graph.
- Công bố giới hạn: dữ liệu chọn theo search/classification, enrichment có
  giới hạn, metadata có thể sai; namespace example.org chưa là LOD public.

## Mapping với 5 yêu cầu capstone

| Bước | Sản phẩm | Tiêu chí có thể kiểm tra |
|---|---|---|
| 1 | requirements, CQs, glossary, ontology-design, res/ontology.ttl | 10 lớp có định nghĩa; quan hệ đúng ngữ nghĩa; CQs chạy; OWL RL kiểm tra |
| 2 | collect_data.py, bronze snapshots + manifest | Metadata thật, URL nguồn và thời điểm thu thập |
| 3 | clean_data.py, transform.py, silver CSV, gold Turtle/RDF/XML | URI HTTP ổn định; vocabulary chuẩn; typed literals; RDF parse được |
| 4 | link_entities.py, linked_output.nt, entity_links.csv | Liên kết OpenAlex/Wikidata/DBpedia có bằng chứng, phản hồi nguồn được lưu |
| 5 | ask.py, queries/, cấu hình Apache Jena Fuseki | SELECT chạy offline và qua SPARQL HTTP endpoint |
