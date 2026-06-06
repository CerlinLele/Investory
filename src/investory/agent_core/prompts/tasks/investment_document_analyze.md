Task:
Execute one investment document analysis To-Do task using upstream extraction results.

Requirements:
{common_rules}
- Use only the provided `document_text`, `document_type`, `analyze_focus`, task metadata, completion criteria, optional `review_goal`, and `dependency_results`.
- Base every finding on upstream extract task results; do not invent facts beyond those results.
- Analyze risks, gaps, inconsistencies, disclosure quality, or document limitations only.
- Do not give buy, sell, hold, timing, suitability, allocation, or return-prediction advice.
- If dependency results are incomplete or insufficient, record the limitation under `information_gaps` or `boundary_notes`.
- Use `supporting_evidence` to point back to extract task ids, cited facts, or source snippets.
- The summary must describe the analysis outcome and limits without making an investment recommendation.

Focus on:
1. Risk or quality findings supported by extracted facts
2. Supporting evidence
3. Information gaps from missing or weak evidence
4. Non-advisory boundary notes
5. Analysis summary

{input_data_block}
