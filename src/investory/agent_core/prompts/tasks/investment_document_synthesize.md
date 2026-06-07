Task:
Synthesize investment document To-Do task results into the final review result.

Requirements:
{common_rules}
- Use only the provided `document_type`, route metadata, optional `review_goal`, `todo_plan`, `todo_results`, and `review_summary`.
- Treat `review_summary` as the deterministic aggregation guide; use `todo_results` for traceable task-level details when needed.
- Preserve the external review structure: extracted facts, risk findings, information gaps, boundary notes, summary, and optional learning next steps.
- Include only facts and findings supported by successful To-Do task results.
- If tasks failed or were skipped, reflect the limitation under `information_gaps` or `boundary_notes`; do not present the review as complete.
- Keep the output non-advisory: no buy, sell, hold, timing, suitability, allocation, or return-prediction advice.
- Use route reason and confidence only as context for document classification, not as evidence for investment conclusions.
- `learning_next_steps` is optional and must stay educational rather than action-oriented.

Focus on:
1. Consolidated extracted facts
2. Consolidated risk findings
3. Information gaps from missing document evidence or failed tasks
4. Boundary notes
5. Final concise summary
6. Optional educational next steps

{input_data_block}
