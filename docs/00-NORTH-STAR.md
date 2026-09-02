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

North Star Metric dài hạn là:

> Tốc độ tạo ra nội dung có ích và tốc độ học được điều gì đúng hơn về người đọc, khách tiềm năng và khách hàng phù hợp với MOTGU.

Các chỉ số vận hành hỗ trợ:

- tỷ lệ bài qua Quality Gate;
- tỷ lệ claim có evidence;
- tỷ lệ human edit sau draft;
- mức độ tái sử dụng evidence và knowledge đúng ngữ cảnh;
- số query/search intent mới mà nội dung bắt được;
- Journal → Artwork / Artist / Visit / Workshop transitions;
- inquiry hoặc hành động có giá trị;
- số learning candidate được xác nhận thành rule;
- regression pass rate sau mỗi thay đổi prompt/model/settings.

## 3. Đường học khách hàng 1–3–6 tháng

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

Chuỗi học:

```text
Potential audience
    ↓
Target audience
    ↓
Core audience
    ↓
Actual user / buyer / visitor
```

## 4. Nguyên tắc ngôn ngữ

ContentEngine không dùng quy trình “viết tiếng Việt rồi dịch sang tiếng Anh” làm mặc định.

Hai ngôn ngữ dùng chung:

- Brief;
- Facts;
- Evidence;
- entities;
- business goal.

Nhưng mỗi ngôn ngữ có writer riêng:

```text
Shared Brief + Evidence
        ├── vi-VN Writer
        └── en Writer
```

Mỗi bản được phép có:

- title khác;
- keyword khác;
- query intent khác;
- ví dụ khác;
- nhịp câu khác;
- cấu trúc nhỏ khác;

miễn không làm thay đổi sự thật cốt lõi.

## 5. Content Engine không phải gì

Không phải:

- máy tạo hàng loạt nội dung;
- công cụ tăng điểm Rank Math;
- hệ thống tạo bài chỉ dựa trên keyword;
- chatbot;
- CRM;
- sales automation;
- kho vector không kiểm soát;
- hệ thống tự sửa prompt mà không có người duyệt.

## 6. Công thức North Star

```text
Useful Problem
+ Specific Audience
+ Reliable Evidence
+ MOTGU Originality
+ Human Voice
+ Clear Structure
+ Search / AI Readability
+ Measurable Action
+ Learning Loop
= Valuable Content
```
