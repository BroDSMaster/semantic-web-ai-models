# Kế hoạch triển khai

Đặc tả: yêu cầu capstone 5 bước của người dùng; phương pháp tại
[ONTOLOGY_ENGINEERING_SKILL.md](../../ONTOLOGY_ENGINEERING_SKILL.md).

1. Viết phạm vi, kịch bản, competency questions, glossary và ontology 10 lớp.
2. Kiểm thử pipeline với fixture nhỏ: định danh, dữ liệu thiếu, quan hệ tác giả
   theo bài, kiểu dữ liệu và liên kết có bằng chứng.
3. Thu thập OpenAlex vào bronze; chuẩn hóa CSV silver; tạo RDF gold.
4. Tra định danh Wikidata/DBpedia; lưu phản hồi nguồn và bảng bằng chứng.
5. Viết SPARQL, CLI, cấu hình Jena Fuseki; chạy kiểm tra offline và endpoint thật.
6. Ghi thống kê thực tế, hướng dẫn chạy và giới hạn trong README.

Giao diện dữ liệu: bronze JSON → silver CSV → gold Turtle/RDF/XML;
res/ontology.ttl + gold + res/linked_output.nt + metadata → graph truy vấn.

Quyết định: thư mục mới được người dùng chỉ định; workspace hiện tại không có
Git repository thực, nên triển khai trực tiếp trong aimodels/, không commit.
Tác giả là Person; Authorship mang vai trò/affiliation theo từng bài. Không
suy ra nơi làm việc hiện tại từ affiliation trong lịch sử bài báo.

Tiêu chí hoàn tất: có dữ liệu nguồn thật; ontology có tài liệu thiết kế;
liên kết thật đến DBpedia; 10 CQ chạy được; OWL RL và kiểm tra cấu trúc;
Jena Fuseki trả lời cùng truy vấn qua HTTP.

## Kết quả triển khai

Đã có đủ ontology engineering docs, 10 lớp, pipeline bronze/silver/gold,
snapshot 200 bài thật, OpenAlex/Wikidata/DBpedia links, CLI, cấu hình Jena
Fuseki, README và hướng dẫn chi tiết. 10 unit tests pass; OWL RL không báo
lỗi; 10 CQs và counts khớp local/Fuseki; offline rebuild tương đương.

Ruling: giữ page size cố định khi phân trang — tránh lặp dữ liệu ở giới hạn
150. Regression test đã quan sát fail rồi pass.
Ruling: loại paratext/collection/book/chapter/report khỏi ResearchPaper —
giữ đúng subclass ScholarlyArticle. Regression test fail rồi pass.
Ruling: chỉ xuất DBpedia links có response xác nhận — public endpoint có
503, nên không ép coverage bằng cách đoán tên resource.

Người dùng yêu cầu hướng dẫn từng bước và không tự chạy thêm. Đã dừng server;
không tiếp tục kiểm tra runtime/persistence sau yêu cầu này. Các kết quả
đã có trước đó được giữ trong res/*-report.json và docs/VALIDATION.md.
