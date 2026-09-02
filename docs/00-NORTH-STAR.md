# 00 — NORTH STAR

## 1. Mục tiêu sản phẩm

ContentEngine giúp MOTGU tạo nội dung chất lượng cao cho website, trước mắt gồm:

- Journal;
- Artwork content.

Mỗi nội dung phải đạt 5 mục tiêu cùng lúc:

1. giải quyết một câu hỏi, nỗi đau, mong muốn hoặc sự tò mò cụ thể của một nhóm người cụ thể;
2. đúng sự thật, có nguồn và có thể truy nguyên;
3. mang giọng, góc nhìn và dữ liệu riêng của MOTGU;
4. dễ hiểu với người đọc, Search và hệ thống AI;
5. tạo tín hiệu đo được để hệ thống học tốt hơn ở chu kỳ tiếp theo.

## 2. Định nghĩa thành công

ContentEngine không được đánh giá bằng số bài tạo ra.

North Star dài hạn là:

> Tạo ra nội dung có ích ngày càng nhanh hơn, đồng thời học được ngày càng chính xác hơn người đọc nào phù hợp với MOTGU và họ thực sự cần gì.

Các chỉ số vận hành hỗ trợ:

- tỷ lệ bài qua Quality Gate;
- tỷ lệ claim quan trọng có evidence;
- tỷ lệ human edit sau draft;
- mức độ tái sử dụng evidence và knowledge đúng ngữ cảnh;
- số query/search intent mới mà nội dung bắt được;
- Journal → Artwork / Artist / Visit / Workshop transitions;
- inquiry hoặc hành động có giá trị;
- số learning candidate được xác nhận thành rule;
- regression pass rate sau mỗi thay đổi prompt/model/settings.

## 3. Reader Transformation

Mỗi content case phải mô tả người đọc trước và sau khi đọc.

Ví dụ:

```text
BEFORE
"Tôi thích tranh nhưng sợ mình không đủ hiểu để chọn."

↓ nội dung

AFTER
"Tôi có thể tự tin nhìn, cảm nhận và bắt đầu chọn tác phẩm phù hợp với mình."
```

Mục tiêu cảm xúc không phải “bơm cảm xúc”. Nó là giúp người đọc chuyển từ một trạng thái thật sang một trạng thái hữu ích hơn.

Mỗi locale có thể có cách diễn đạt khác nhưng không được làm sai reader value cốt lõi.

## 4. Đường học khách hàng 1–3–6 tháng

### 0–1 tháng — khám phá rộng

Mục tiêu: kiểm chứng nhiều vấn đề nhỏ, không vội khóa persona.

Đầu ra:

- nhiều Audience Hypothesis;
- nhiều Problem/Desire;
- nhiều Content Hypothesis;
- dữ liệu hành vi ban đầu.

### 1–3 tháng — tìm tín hiệu

Mục tiêu: tìm nhóm nội dung và nhóm người có tín hiệu tốt hơn.

Đầu ra:

- query clusters;
- content clusters;
- audience signals;
- hành vi chuyển tiếp;
- nhóm vấn đề có tiềm năng cao.

### 3–6 tháng — thu hẹp

Mục tiêu: chuyển từ khách tiềm năng rộng sang nhóm có xác suất phù hợp cao hơn.

```text
Potential audience
    ↓
Target audience
    ↓
Core audience
    ↓
Actual user / buyer / visitor
```

Không thu hẹp chỉ từ một bài hoặc một tín hiệu nhỏ. Hệ thống phải biết nói “chưa đủ dữ liệu để kết luận”.

## 5. Nguyên tắc ngôn ngữ

ContentEngine không dùng quy trình “viết tiếng Việt rồi dịch sang tiếng Anh” làm mặc định.

Một `ContentCase` giữ phần chung:

- audience/problem;
- business goal;
- core facts;
- evidence;
- originality;
- content hypothesis.

Mỗi ngôn ngữ có `LocaleVariant` riêng:

```text
ContentCase
    ├── vi-VN LocaleVariant
    └── en LocaleVariant
```

Mỗi variant được phép có:

- title khác;
- keyword/query khác;
- intent nuance khác;
- ví dụ khác;
- nhịp câu khác;
- cấu trúc nhỏ khác;

miễn không làm thay đổi sự thật cốt lõi.

## 6. Content Engine không phải gì

Không phải:

- máy tạo hàng loạt nội dung;
- công cụ tăng điểm Rank Math;
- hệ thống tạo bài chỉ dựa trên keyword;
- chatbot;
- CRM;
- sales automation;
- kho vector không kiểm soát;
- hệ thống tự sửa prompt mà không có người duyệt;
- hệ thống tự chấm điểm rồi tự tin rằng output đã tốt.

## 7. Công thức North Star

```text
Useful Problem
+ Specific Audience
+ Reader Transformation
+ Reliable Evidence
+ MOTGU Originality
+ Human Voice
+ Clear Structure
+ Search / AI Readability
+ Measurable Action
+ Learning Loop
= Valuable Content
```
