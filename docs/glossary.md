# Glossary và quyết định class/instance/value

Glossary này dành cho nhánh nghiên cứu. Glossary catalog model/API mới nằm
trong [MODEL_ONTOLOGY.md](MODEL_ONTOLOGY.md).

| Thuật ngữ ưu tiên | Định nghĩa | Đồng nghĩa / ví dụ | Phân loại và điểm dễ nhầm |
|---|---|---|---|
| ResearchPaper | Công trình nghiên cứu có bản ghi OpenAlex work | Paper, scholarly work; một bài LLM | Class; preprint cũng có thể là công trình; không khẳng định mọi bài đều peer-reviewed |
| Person | Một người được đại diện bởi OpenAlex author ID | Human, tác giả trong dữ liệu | Class; “researcher/author” là vai trò, không là định danh vĩnh viễn |
| ResearchInstitution | Tổ chức xuất hiện trong affiliation của tác giả | University, lab, company | Class theo vai trò trong mẫu; MIT là instance; không phải Person |
| PublicationSource | Venue/kho lưu trữ xuất hiện trong primary location | Journal, conference, repository; arXiv | Class; không đồng nhất với Publisher hoặc một ResearchPaper |
| Publisher | Tổ chức xuất bản có OpenAlex publisher ID | Publishing organization | Class vai trò tổ chức; chỉ host có ID P mới ánh xạ, không ép host I thành publisher |
| ResearchTopic | Khái niệm chủ đề chi tiết của OpenAlex | Topic; một chủ đề language modeling | Class các concept; bản thân chủ đề cụ thể là instance, không là paper |
| ResearchSubfield | Nhóm khái niệm topic trong phân loại | Subfield; Artificial Intelligence | Class các concept; liên hệ “inSubfield”, không phải Topic subclassOf Subfield |
| ResearchField | Nhóm subfield | Field; Computer Science | Class các concept; Computer Science là instance |
| ResearchDomain | Cấp phân loại rộng nhất | Domain; Physical Sciences | Class các concept; đây không phải tên miền Internet |
| Authorship | Sự tham gia của một người vào một bài | Author participation | Class association/role, ID = work+author; chứa affiliation và first/middle/last |
| Affiliation | Quan hệ tác giả–tổ chức trong bối cảnh một bài | Institutional affiliation | Object property của Authorship; không tạo class thứ 11 và không suy ra việc làm hiện tại |
| Citation count | Số lần được trích dẫn theo OpenAlex ở lúc lấy mẫu | cited_by_count | Literal nonNegativeInteger; khác số tài liệu mà bài trích dẫn |
| Reference | Công trình mà bài trích dẫn | Bibliographic reference | Relation dcterms:references; URI ngoài mẫu có thể chưa có label/metadata local |
| DOI / ORCID / ROR | Định danh công trình / người / tổ chức | DOI resolver, researcher ID, organization ID | URI values; thiếu thì bỏ; không tạo một class chỉ để tăng số lớp |
| Quốc gia | Mã quốc gia của institution | VN, US | Literal ISO code theo nguồn; không phải quốc tịch của tác giả |
| Open access | Cờ trạng thái truy cập mở theo nguồn | is_oa | Boolean; không có nghĩa metadata và toàn văn có chung giấy phép |
| sameAs | Hai URI cùng chỉ một thực thể | Identity link | Không phải “tương tự”, “liên quan” hoặc “bài viết nói về” |

Tên gần giống nhau không chứng minh hai người/tổ chức là cùng một thực thể.
OpenAlex IDs, Wikidata QIDs và metadata nguồn là cơ sở nhận diện trong dự án.
