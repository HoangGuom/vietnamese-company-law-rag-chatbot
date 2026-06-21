# Local evaluation methodology

Thư mục này đánh giá **toàn bộ pipeline RAG**, không chỉ riêng Qwen. Pipeline được
tách thành ba tầng:

1. **Guard/abstention:** quyết định trả lời hay từ chối.
2. **Retrieval:** chọn và xếp hạng chunk pháp luật.
3. **Generation/policy:** tạo câu trả lời, citation và kiểm tra grounding.

Khi sửa rule, threshold, keyword boost, prompt hoặc deterministic answer, metric
của pipeline có thể thay đổi dù trọng số của Qwen không hề được huấn luyện lại.

## Chạy evaluator

```powershell
# Guard + retrieval, không gọi Qwen
.\.venv\Scripts\python.exe local_eval\rag_eval_local.py

# Full pipeline, gồm generation
.\.venv\Scripts\python.exe local_eval\rag_eval_local.py --generate
```

Test set mặc định nằm tại
[`local_eval/cases/rag_eval_cases.jsonl`](cases/rag_eval_cases.jsonl). Mỗi case
ghi rõ category, expected accept/reject, chunk kỳ vọng, required terms và mức độ
nghiêm trọng. Không nên sửa expected result chỉ để làm điểm số tăng; thay đổi nhãn
phải dựa trên việc kiểm tra lại văn bản pháp luật.

## Nguồn phương pháp

| Thành phần | Nguồn tham khảo | Cách dự án sử dụng |
|---|---|---|
| Kiến trúc RAG | Lewis et al., “Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks”, NeurIPS 2020: <https://proceedings.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html> | Tách bộ nhớ tham số của model khỏi kho văn bản được truy xuất và cung cấp provenance. Dự án dùng embedding retriever + Qwen, không tái hiện kiến trúc huấn luyện của paper. |
| Đánh giá RAG theo nhiều tầng | Es et al., “RAGAS: Automated Evaluation of Retrieval Augmented Generation”, EACL 2024: <https://aclanthology.org/2024.eacl-demo.16/> | Lấy cảm hứng từ việc đánh giá retrieval, answer quality và grounding riêng biệt. Các metric trong dự án là deterministic/local, không phải implementation RAGAS. |
| Precision/Recall | NIST TREC, “Common Evaluation Measures”: <https://trec.nist.gov/pubs/trec10/appendices/measures.pdf> | Dùng cho guard confusion matrix và retrieval judgments. |
| Reciprocal rank/MRR | Voorhees, “The TREC-8 Question Answering Track Evaluation”: <https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=151495> | Đo vị trí của chunk liên quan đầu tiên. |
| Reject option/selective prediction | Geifman & El-Yaniv, “Selective Classification for Deep Neural Networks”, 2017: <https://arxiv.org/abs/1705.08500> | Guard đóng vai trò abstention policy. Dự án theo dõi coverage và selective risk, nhưng guard là rule-based chứ không phải phương pháp SelectiveNet trong paper. |
| Evidence-grounded verification | Thorne et al., “FEVER: a Large-scale Dataset for Fact Extraction and VERification”, NAACL 2018: <https://aclanthology.org/N18-1074/> | Lấy cảm hứng từ yêu cầu claim phải đi kèm evidence. Dự án kiểm tra citation index và legal identifier có xuất hiện trong context. |

## Metric guard/abstention

Quy ước:

- Positive = câu hỏi hợp lệ mà chatbot nên trả lời.
- Negative = câu ngoài phạm vi/mơ hồ/nguy hiểm mà chatbot nên từ chối.
- TP = accept đúng; TN = reject đúng; FP = accept nhầm; FN = reject nhầm.

| Metric | Công thức | Tốt khi | Tác động/kỹ thuật liên quan |
|---|---|---|---|
| `guard_decision_accuracy` | `(TP + TN) / N` | Cao | Tổng quan, nhưng có thể gây hiểu nhầm nếu tập test mất cân bằng. |
| `guard_precision` | `TP / (TP + FP)` | Cao | Giảm khi guard cho câu ngoài phạm vi đi qua. Tăng threshold/rule chặn có thể cải thiện metric này. |
| `guard_recall` | `TP / (TP + FN)` | Cao | Giảm khi guard quá chặt và chặn câu pháp luật hợp lệ. Nới rule/threshold có thể cải thiện recall nhưng làm precision giảm. |
| `guard_f1` | trung bình điều hòa precision và recall | Cao | Dùng khi cần cân bằng false accept và false reject. |
| `guard_specificity` | `TN / (TN + FP)` | Cao | Khả năng từ chối đúng câu không thuộc phạm vi. |
| `false_acceptance_rate` | `FP / số case negative` | Thấp | Quan trọng với chatbot pháp luật vì accept nhầm có thể dẫn đến câu trả lời không có căn cứ. |
| `false_rejection_rate` | `FN / số case positive` | Thấp | Cao nghĩa là người dùng hỏi đúng nhưng không được phục vụ. |
| `answer_coverage` | `số case được accept / N` | Không có mức “càng cao càng tốt” | Phải đọc cùng selective risk. Coverage quá thấp có thể an toàn nhưng chatbot gần như không trả lời. |
| `selective_risk` | `FP / số case được accept` | Thấp | Rủi ro lỗi guard trong tập các câu mà hệ thống quyết định trả lời. |
| `fallback_accuracy` | tỷ lệ reject trả đúng fallback và không có chunk | Cao | Đo wiring Python/API, không đo chất lượng Qwen. |
| `rewrite_accuracy` | tỷ lệ rewrite khớp annotation | Cao | Rule sửa typo/small-talk. Rewrite quá mạnh có thể làm sai ý người dùng. |

`fallback_correct` chỉ áp dụng cho case cần reject. Với case positive, việc model
rơi về fallback được ghi riêng bằng `response_non_fallback` và kéo giảm các metric
generation như citation/required-term; nó không được trộn vào guard score.

### Chọn threshold guard/retrieval

Không tối ưu một metric đơn lẻ. Ví dụ tăng `MIN_RETRIEVAL_SCORE` thường:

- giảm false acceptance;
- nhưng có thể tăng false rejection và giảm answer coverage.

Nên chọn cấu hình trên tập validation riêng, ưu tiên ràng buộc an toàn trước
(ví dụ false acceptance thấp), sau đó tối đa guard recall/coverage trong phạm vi
rủi ro chấp nhận được.

## Metric retrieval

Các metric chỉ được tính khi case có `expected_chunk_ids`.

| Metric | Công thức/ý nghĩa | Tốt khi | Giới hạn |
|---|---|---|---|
| `retrieval_hit_rate_at_k` | Có ít nhất một chunk kỳ vọng trong Top K | Cao | Không cho biết đã lấy đủ evidence hay chưa. |
| `retrieval_recall_at_k` | `số expected chunks tìm thấy / tổng expected chunks` | Cao | Phụ thuộc annotation có liệt kê đủ evidence liên quan hay không. |
| `judged_retrieval_precision_at_k` | `số expected chunks tìm thấy / số chunks trả về` | Cao | Đây là **judged precision** trên nhãn chưa đầy đủ; chunk không được ghi expected chưa chắc là sai. |
| `retrieval_mrr` | `1 / rank` của expected chunk đầu tiên, trung bình qua các query | Cao | Chỉ quan tâm hit đầu tiên; không đo đầy đủ nhiều evidence. |
| `retrieval_ms_avg/p50/p95` | latency retrieval trung bình, trung vị và đuôi chậm 95% | Thấp, sau khi giữ chất lượng | P95 phản ánh trải nghiệm các request chậm tốt hơn chỉ dùng trung bình. Không nên đổi chất lượng lấy tốc độ mà không theo dõi Recall/MRR. |

Thay embedding model, `top_k`, keyword boost, deduplication, score threshold,
top-score gap hoặc reranker sẽ tác động trực tiếp nhóm metric này.

## Metric generation và grounding

| Metric | Ý nghĩa | Tốt khi | Tác động/kỹ thuật liên quan |
|---|---|---|---|
| `citation_presence_rate` | Câu trả lời positive có ít nhất một citation | Cao | Prompt, structured output và post-processing. Có citation chưa đồng nghĩa nội dung đúng. |
| `citation_precision` | Tỷ lệ citation index nằm trong danh sách chunk thực tế | Cao | Chặn `[99]` hoặc index không tồn tại. Chưa đo entailment giữa claim và chunk. |
| `generation_success_rate` | Tỷ lệ case positive gọi generation không gặp lỗi hạ tầng/runtime | Cao | Phân biệt lỗi Ollama/network với lỗi chất lượng câu trả lời. |
| `response_non_fallback_rate` | Tỷ lệ case positive tạo được câu trả lời thay vì fallback | Cao | Giảm khi validator quá chặt hoặc model không tuân thủ output policy. |
| `required_term_score` | Tỷ lệ required terms xuất hiện sau chuẩn hóa | Cao | Metric lexical tùy biến; dễ bỏ sót paraphrase và không chứng minh factual correctness. |
| `identifier_grounding_score` | Không có số điều/văn bản/mẫu ngoài context | Cao | Giảm hallucination định danh pháp lý; không kiểm tra toàn bộ mệnh đề. |
| `no_advice_score` | Không xuất hiện mẫu lời khuyên bị cấm | Cao | Prompt/policy checker; có thể false positive hoặc bỏ sót cách diễn đạt mới. |
| `no_reasoning_leak_score` | Không lộ marker suy luận nội bộ | Cao | Không phải metric “độ ngắn”; chỉ đo leak theo danh sách marker. |
| `direct_verdict_compliance` | Câu xác nhận mở đầu Đúng/Sai/Có/Không và có giải thích | Cao | Prompt, validator, retry hoặc deterministic answer. |
| `generation_ms_avg/p50/p95` | latency generation trên các case positive được accept | Thấp, sau khi giữ chất lượng | Phụ thuộc model, phần cứng, số token và số lần retry. |
| `accepted_total_ms_avg/p50/p95` | latency end-to-end của các câu hỏi hợp lệ được hệ thống trả lời | Thấp, sau khi giữ chất lượng | Đây là nhóm nên dùng khi mô tả trải nghiệm chatbot; không trộn request bị từ chối rất nhanh vào latency trả lời. |
| `total_ms_avg` | latency toàn bộ test set, gồm cả request bị từ chối | Thấp, sau khi giữ chất lượng | Có thể nhìn đẹp giả tạo nếu test set có nhiều case bị guard từ chối nhanh. |

Hiện dự án **chưa có** human evaluation, claim-level entailment, answer correctness
theo đáp án chuẩn, BERTScore hoặc LLM-as-a-judge. Vì vậy không được diễn giải các
metric trên thành “Qwen chính xác 100%”.

## Metric tùy biến của dự án

`case_score`, `overall_score` và `severity_weighted_score` là composite metric do
dự án tự định nghĩa. Trọng số hiện tại ưu tiên guard + retrieval, sau đó mới đến
citation/policy. Chúng hữu ích để regression-test một cấu hình, nhưng:

- không phải metric chuẩn của RAGAS, TREC hay paper RAG;
- không thể so trực tiếp với điểm của dự án khác;
- có thể tăng do overfit test case;
- phải luôn đọc cùng các metric thành phần và số lượng/category của case.

## Quy trình so sánh kỹ thuật

1. Giữ nguyên test set và annotation.
2. Chạy baseline, lưu report.
3. Chỉ thay một nhóm kỹ thuật: threshold, embedding, reranker, prompt...
4. Chạy lại cả retrieval-only và full generation.
5. So sánh theo category, không chỉ `overall_score`.
6. Kiểm tra trade-off:
   - guard precision so với guard recall/coverage;
   - Recall@K/MRR so với latency;
   - citation/grounding so với fallback hoặc retry rate.
7. Đọc thủ công các case thất bại trước khi chọn cấu hình.

## Giới hạn của test set

- Đây là tập regression cục bộ, không phải benchmark pháp luật độc lập.
- Một phần case được tạo sau khi đã biết cấu trúc dữ liệu, nên có nguy cơ overfit.
- Expected chunks chưa phải relevance judgment đầy đủ.
- Required terms là kiểm tra lexical đơn giản.
- Điểm tốt cần được xác nhận trên holdout cases và đánh giá thủ công bởi người có
  chuyên môn pháp lý trước khi triển khai thực tế.
