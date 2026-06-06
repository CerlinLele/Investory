Task:
Execute one investment document extraction To-Do task.

Requirements:
{common_rules}
- Use only the provided `document_text`, `document_type`, `extract_focus`, task metadata, completion criteria, and optional `review_goal`.
- Extract facts only; do not analyze, compare, recommend, predict returns, or infer suitability.
- Ground every extracted fact in the provided document.
- Include source citations as document snippets, section names, table labels, or other source references available in the text.
- If a requested fact is not present, record it under `information_gaps`.
- Keep `boundary_notes` focused on source limits and non-advisory boundaries.
- The summary must describe what was extracted, not whether the investment is good or bad.

Focus on:
1. Document-grounded facts
2. Source citations
3. Information gaps
4. Boundary notes
5. Factual extraction summary

{input_data_block}
