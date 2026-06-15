Task:
Review the investment-related document in a single pass using the provided review framework.

Requirements:
{common_rules}
- Use only the provided `document_text`, `document_type`, `extract_focus`, `analyze_focus`, and optional `review_goal`.
- Ground every extracted fact and risk finding in the document itself.
- If the document does not support a conclusion, record it under `information_gaps` instead of filling the gap.
- Do not give buy, sell, hold, timing, suitability, allocation, or return-prediction advice.
- Keep `boundary_notes` focused on source limits, uncertainty, and non-advisory boundaries.
- `learning_next_steps` is optional and must stay educational rather than action-oriented.

Focus on:
1. Extracted facts
2. Risk findings
3. Information gaps
4. Boundary notes
5. Summary
6. Optional learning next steps

{input_data_block}
