# 11 — RESEARCH & SEARCH SPEC

## Signal → Hypothesis → Opportunity boundary

Discovery đầu ra là Signal/NeedHypothesis proposal → Opportunity Map → human selection.
Keyword Plan là công cụ con. Observation không chứa diễn giải như fact; SearchSignal
là payload provider, chưa phải Signal normalized hoặc nhu cầu khách đã kiểm chứng.

Ưu tiên tìm tín hiệu khách tiềm năng: (1) Reddit/travel forums; (2) TripAdvisor/Google
Maps reviews; (3) gallery/workshop/art-tour reviews; (4) YouTube/public communities;
(5) PAA/Related/Autocomplete; (6) competitor FAQ/sales pages. Đây là thứ tự khám phá,
không phải authority ranking. Không coi vài review là đại diện thị trường/MOTGU.

Mọi Deep Research về nhu cầu phải trả SUPPORT, CONTRADICTION, ALTERNATIVE EXPLANATION
và MISSING EVIDENCE, kèm source refs; nếu chưa tìm được phản bác thì ghi rõ phạm vi đã
tìm, không bịa một phản bác. Report tổng hợp không thay nguồn gốc.

Ví dụ inquiry "Can you ship this to Australia?" hỗ trợ nhu cầu thông tin giao hàng,
không tự chứng minh sợ lừa đảo. Xem Artwork bốn phút có thể là quan tâm, khó hiểu hoặc
tab mở. Số nguồn độc lập phải loại repost/cùng lời kể; không chỉ đếm URL.

### Provider scope trong PR-B / PR-C

Giữ Serper → Tavily → Exa → Jina, Brave optional; không thêm provider mới.
Serper dùng SEARCH DISCOVERY cho PAA/Related/Autocomplete và MARKET DISCOVERY với query
nhắm forum/review như `site:reddit.com buying art Hanoi`. Hai chế độ query không biến
search snippet thành review gốc: chỉ normalize MARKET khi đọc được observation có locator.
PR-B vẫn chỉ chạy provider spike; orchestration hai hướng và Signal extraction thuộc PR-C.

Tavily domain filters và Exa specialized search là ứng viên tối ưu sau pilot, không phải
dependency mới hoặc mặc định gọi deep. Chỉ cân nhắc adapter chuyên biệt sau 3–5 runs có
evidence về coverage thiếu. Trang bị chặn/không đọc được phải ghi gap hoặc manual review.

### Jina structured reader contract (PR-B)

- Request `Accept: application/json`, `X-With-Links-Summary: true`, `X-Base: final`.
- Giữ requested URL và URL provider trả (nullable khi thiếu), title, content,
  `publishedTime`/provider timestamp nếu có và captured_at của hệ thống; không bịa
  publication date. Nếu provider trả upstream `httpStatus >= 400`, coi là read failure.
- Normalize links có giới hạn; feed cả links và content vào second-hop, giữ parent URL.
- `X-Token-Budget` cấu hình theo request; vượt budget làm request FAIL, không tự cắt
  token hay tự retry với budget cao hơn. Local content/raw-excerpt bounds vẫn độc lập.
- Malformed/empty/non-JSON response hoặc unsafe final URL phải thành error artifact;
  không đánh dấu HTML lỗi/challenge là document đã đọc thành công.
- Link chỉ là candidate, không phải factual evidence; metadata/raw payload giữ bounded.

Nguồn kỹ thuật: https://jina.ai/reader/ và
https://github.com/jina-ai/reader/blob/main/README.md (kiểm tra 2026-09-05).

## 1. Mục tiêu

Research của ContentEngine phải giúp trả lời hai câu hỏi khác nhau:

1. **Discovery Research** — người đọc đang hỏi gì, lo gì, muốn gì, Internet đang trả lời ra sao và còn khoảng trống nào;
2. **Evidence Research** — một thông tin có đúng không, nguồn gốc ở đâu, nguồn nào mạnh nhất và có nguồn nào phản bác không.

Không trộn hai mục tiêu này.

Một câu xuất hiện nhiều trên Google không tự trở thành fact. Một nguồn học thuật tốt cũng không tự chứng minh đó là điều khách hàng quan tâm.

## 2. Search stack V1 đã chốt

### Serper — nguồn chính để nhìn Google

Dùng cho:

- organic results;
- People Also Ask;
- Related Searches;
- Autocomplete khi endpoint/phương thức phù hợp;
- title/snippet/domain để hiểu bức tranh kết quả tìm kiếm.

Vai trò chính: **phát hiện nhu cầu tìm kiếm và mở rộng câu hỏi**.

Không mặc định coi top 1–5 là nguồn tốt.

### Tavily — tìm nguồn nghiên cứu phù hợp

Dùng khi:

- Google trả nhiều trang bán hàng/SEO;
- cần tìm nguồn có nội dung sát câu hỏi hơn;
- cần một lượt research rộng nhưng có giới hạn.

Vai trò chính: **source discovery**.

### Exa — tìm nguồn sâu theo ý nghĩa

Dùng khi:

- cần bài viết/nghiên cứu tương tự một nguồn tốt;
- keyword search thông thường nhiều nhiễu;
- cần tìm second-hop source, expert, institution hoặc bài sâu liên quan.

Vai trò chính: **semantic discovery + second-hop discovery**.

### Jina Reader — đọc trang đã chọn

Dùng sau khi URL đã qua lọc ban đầu:

- lấy nội dung sạch;
- giảm navigation/boilerplate;
- tạo SourceDocument để bóc tách claim/knowledge;
- giữ URL và provenance.

Jina không quyết định nguồn có đáng tin hay không. Nó là **reader/extractor**, không phải authority judge.

### Brave — optional coverage check

Không dùng làm nguồn chính trong V1.

Chỉ dùng khi:

- muốn kiểm tra một góc web khác;
- Serper/Tavily/Exa không đủ coverage;
- debug provider outage.

Mặc định `disabled` trong normal research path.

### SerpAPI / Google Custom Search

Không nằm trong default stack V1.

Chỉ mở lại nếu sau pilot có một nhu cầu cụ thể mà Serper/Tavily/Exa không đáp ứng tốt.

## 3. Nguyên tắc dùng API

Không gọi tất cả provider cho mọi query.

Dùng chiến lược **rẻ trước, đủ thì dừng**:

```text
Seed / Question
    ↓
Search MOTGU Knowledge trước
    ↓
SERPER
    ↓
đã đủ discovery signal?
   ├── YES → source selection
   └── NO  → TAVILY
                ↓
          cần nguồn sâu hơn?
             ├── NO → source selection
             └── YES → EXA
                         ↓
                    source selection
                         ↓
                       JINA
```

Brave chỉ là fallback/coverage check.

Mọi call phải có budget và log provider, query, thời gian, số kết quả và lỗi.

## 4. Không tin thứ hạng tìm kiếm

`rank_position` là tín hiệu về Search, không phải tín hiệu authority.

Một URL top 1 có thể là sales page yếu về evidence.

Nguồn được đánh giá theo nhiều chiều:

- source type;
- author/organization rõ hay không;
- commercial bias;
- primary hay secondary;
- có citation/source gốc không;
- freshness;
- relevance với câu hỏi;
- có nguồn khác xác nhận hay phản bác;
- authority theo loại claim.

Không gộp tất cả thành một điểm tuyệt đối rồi tin máy móc.

## 5. Source buckets

Research nên phân nguồn thành các nhóm để dùng đúng việc.

### Audience / discovery sources

Ví dụ:

- Search queries/PAA/Related;
- Reddit/community;
- travel forum;
- reviews;
- customer questions;
- Search Console sau này.

Dùng để hiểu:

- ngôn ngữ khách dùng;
- pain/desire;
- objection;
- confusion;
- question patterns.

Không mặc định dùng làm factual evidence.

### Factual / authority sources

Ví dụ:

- MOTGU canonical data;
- primary source;
- artist-approved source;
- museum;
- institution;
- academic paper;
- government/official source;
- high-trust report.

Dùng để kiểm chứng facts/claims theo authority rule.

### Market / competitor sources

Ví dụ:

- gallery sales pages;
- competitors;
- tourism commerce pages;
- SEO articles.

Dùng để hiểu:

- đối thủ đang trả lời gì;
- pattern thị trường;
- content gap;
- commercial framing.

Không dùng làm authority cao chỉ vì rank tốt.

## 6. Discovery Research flow

```text
ContentCase / Seed Topic
    ↓
MOTGU Knowledge Recall
    ↓
Seed Query Set
    ↓
Serper: PAA + Related + Organic + Autocomplete
    ↓
normalize + dedupe
    ↓
query/question expansion
    ↓
Tavily / Exa khi cần
    ↓
Audience / Problem / Intent classification
    ↓
Keyword Plan
    ↓
Discovery Research Report
```

Discovery Research phải trả lời tối thiểu:

- khách có thể đang hỏi những câu gì;
- các câu hỏi gom thành nhóm nào;
- intent nào đang xuất hiện;
- top results đang nghiêng về loại nội dung nào;
- điểm nào Internet trả lời chung chung hoặc bán hàng quá mức;
- MOTGU có khả năng nói điều gì khác biệt;
- cần Evidence Research gì tiếp theo.

## 7. Evidence Research flow

```text
Claim / Question cần xác minh
    ↓
MOTGU canonical/internal source
    ↓
Primary / high-authority source search
    ↓
Tavily / Exa source discovery khi cần
    ↓
Jina đọc selected URLs
    ↓
second-hop: đi tới source gốc/citation
    ↓
Claim ↔ Evidence
    ↓
Contradiction check
    ↓
EvidenceSet
```

Nguyên tắc:

- ưu tiên source gốc hơn bài tổng hợp;
- một SEO article tốt có thể dùng như bản đồ để tìm primary source;
- nếu nguồn mâu thuẫn, giữ contradiction thay vì che đi;
- không viết trước rồi tìm nguồn để hợp thức hóa;
- EvidenceSet chỉ chứa evidence đã được chọn theo contract.

## 8. Second-hop research

Một URL tốt không phải điểm kết thúc.

ContentEngine phải có khả năng bóc:

- cited report;
- named expert;
- museum/institution;
- book/paper;
- original interview;
- original dataset;
- source links.

Sau đó tạo query mới để tìm nguồn gốc.

Ví dụ:

```text
SEO article
→ dẫn Art Basel report
→ tìm report gốc
→ dùng report gốc làm evidence
```

Đây là cách chính để thoát khỏi lớp top results bán hàng/SEO.

## 9. Manual Deep Research

ChatGPT Pro/Gemini Pro Deep Research được coi là **human-assisted research tool**, không phải dependency bắt buộc.

Dùng khi:

- pillar quan trọng;
- chủ đề văn hóa/lịch sử phức tạp;
- nhiều nguồn mâu thuẫn;
- cần nghiên cứu một giả thuyết chiến lược;
- cần pre-mortem/counter-research.

ContentEngine có thể tạo `DeepResearchBrief` để người dùng mang sang ChatGPT/Gemini.

Khi report quay lại:

```text
Report
+ Source URLs
    ↓
import như research artifact
    ↓
extract findings
    ↓
follow original sources
    ↓
Knowledge Candidates / Evidence
```

**Bản kết luận của Deep Research không tự trở thành factual evidence.** Nguồn gốc được report dẫn tới mới được đánh giá theo authority rules.

## 10. Counter Research

Với giả thuyết quan trọng, khuyến nghị hai chiều:

```text
SUPPORT RESEARCH
Điều gì chứng minh giả thuyết đúng?

COUNTER RESEARCH
Điều gì chứng minh giả thuyết sai?
```

Mục tiêu không phải tạo tranh luận giả mà để phát hiện:

- objection;
- logistics friction;
- trust gap;
- cultural barrier;
- price concern;
- reason not to act.

Những friction này thường là nguồn content opportunity tốt.

## 11. Knowledge ingest sau research

Không đổ toàn bộ search result/raw HTML vào Obsidian.

Pipeline:

```text
RAW PROVIDER RESULT / PAGE
    ↓
Source + SourceDocument
    ↓
extract candidate knowledge
    ↓
dedupe / link / provenance
    ↓
Knowledge Candidate
    ↓
review/admission
    ↓
Approved Knowledge
    ↓
Obsidian mirror khi hữu ích
```

### Raw

Giữ ở artifact/source store phục vụ audit và re-process. Không làm nhiễu Obsidian.

### Candidate

AI đã bóc tách nhưng chưa đủ tin để tái sử dụng như truth.

### Approved

Được phép retrieval/tái sử dụng theo authority/freshness rule.

## 12. Atomic Knowledge Card

Một card nên chứa một ý đủ nhỏ để tái sử dụng và liên kết.

Ví dụ frontmatter:

```yaml
id: knowledge-00128
project: motgu
status: candidate
type: customer_question
locale: en
statement: "First-time art buyers often worry about choosing the wrong painting."
audience: first-time-art-buyer
problem: fear-of-choosing-wrong
topic: buying-art
source_refs:
  - source-0042
authority: discovery_signal
commercial_bias: low
freshness: 2026-09-02
research_run: research-0021
entities:
  - artwork
```

Card phải link được về source refs; không chỉ lưu một đoạn AI summary không nguồn.

## 13. Obsidian role

Obsidian là **human-readable knowledge mirror/workspace**, không phải nơi tự nhiên trở thành truth chỉ vì file tồn tại.

Gợi ý cấu trúc:

```text
00_Inbox/
10_Knowledge/
20_Topics/
30_Research/
40_Published/
```

- `00_Inbox`: candidate cần xem;
- `10_Knowledge`: approved atomic cards;
- `20_Topics`: summary/hub do hệ thống tạo từ approved knowledge;
- `30_Research`: report quan trọng/manual deep research;
- `40_Published`: content final nếu muốn mirror.

Raw SERP/API payload không đưa vào vault mặc định.

## 14. Freshness

Mỗi knowledge/evidence item cần biết có dễ cũ không.

Phân loại tối thiểu:

- `stable`: lịch sử, kỹ thuật nghệ thuật cơ bản;
- `review_periodic`: market/report/travel information;
- `live`: price, stock, availability, opening information.

`live` data không dùng từ memory nếu có canonical live source.

## 15. Provider fallback

Provider failure không được làm workflow mất dữ liệu.

Ví dụ:

- Serper lỗi → Tavily discovery fallback;
- Tavily lỗi → Exa nếu task phù hợp;
- Jina lỗi → fetch/read adapter khác hoặc manual source review;
- provider quota hết → explicit `provider_budget_exhausted`, không loop vô hạn.

Không cần đảm bảo mọi provider trả cùng dữ liệu.

## 16. Cost control

Mỗi research run đặt giới hạn:

- max seed queries;
- max query expansion depth;
- max provider calls;
- max selected URLs;
- max pages read;
- max second-hop depth;
- max total cost;
- stop-when-sufficient rule.

V1 mặc định chỉ mở rộng PAA/query một hoặc hai tầng. Không crawl vô hạn.

## 17. Research artifacts

Structured outputs tối thiểu:

- `seed_query_set`;
- `serp_signal_set`;
- `source_candidate_set`;
- `selected_source_set`;
- `discovery_research_report`;
- `evidence_research_report`;
- `knowledge_candidate_set`;
- `keyword_plan`;
- `evidence_set`.

## 18. Definition of done V1

Research/Search contract đạt khi:

- default provider roles rõ;
- không tin top search position như authority;
- Discovery và Evidence Research tách biệt;
- source selection có commercial-bias/authority awareness;
- second-hop có đường tới source gốc;
- raw data không làm bẩn Obsidian;
- knowledge card giữ provenance;
- manual ChatGPT/Gemini Deep Research nhập lại được mà không biến report thành truth;
- provider budget/fallback rõ;
- Keyword Plan nhận được signal chuẩn hóa từ Discovery Research.
