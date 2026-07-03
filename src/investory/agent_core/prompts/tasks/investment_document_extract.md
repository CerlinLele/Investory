Task:
Execute one investment document extraction To-Do task.

Requirements:
{common_rules}
- Use only the provided `document_text`, `document_type`, `extract_focus`, task metadata, completion criteria, optional `review_goal`, and any chunk metadata (`chunk_index`, `chunk_count`, `review_scope`).
- When `review_scope` is `document_chunk`, treat `document_text` as one chunk of the source document and extract lightweight structured evidence from that chunk only.
- Extract facts only; do not analyze, compare, recommend, predict returns, or infer suitability.
- Ground every extracted fact in the provided document.
- Include source citations as document snippets, section names, table labels, or other source references available in the text.
- If a requested fact is not present, record it under `information_gaps`.
- Visual-only redundancy rule: If a graphical element (e.g., a performance growth chart, pie chart, or diagram) presents the same quantitative data that is otherwise available in extracted text, tables, or structured fields, note it under `boundary_notes` as "visual-only representation" rather than `information_gaps`. Example: "The $10,000 growth chart visualizes the same annual returns data already captured in the performance table; chart rendering details are not captured by text extraction."
- Keep `boundary_notes` focused on source limits and non-advisory boundaries.
- The summary must describe what was extracted, not whether the investment is good or bad.

Focus on:
1. Document-grounded facts
2. Source citations
3. Information gaps
4. Boundary notes
5. Factual extraction summary

{input_data_block}
