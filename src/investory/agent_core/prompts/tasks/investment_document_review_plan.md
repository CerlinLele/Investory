Task:
Generate a structured To-Do plan for reviewing the investment-related document.

Requirements:
{common_rules}
- Use only the provided `document_text`, `document_type`, `extract_focus`, `analyze_focus`, and optional `review_goal`.
- Keep the plan within investment document review boundaries; do not create buy, sell, hold, timing, suitability, allocation, return-prediction, real-time market data, or personalized advice tasks.
- Create stable, short task ids such as `extract_fees`, `extract_holdings`, or `analyze_fee_disclosure`.
- Prefer 4 to 8 total tasks for long documents; keep shorter documents smaller.
- Use `investment_document_extract` for factual extraction tasks.
- Extract tasks must only extract document-grounded facts and must use `depends_on=[]`.
- Use `investment_document_analyze` for analysis tasks.
- Analyze tasks must depend on at least one extract task and must judge only from upstream extracted facts.
- Every task must have a clear title, description, payload, and non-empty `completion_criteria`.
- The plan summary should explain the review strategy without making an investment recommendation.

Focus on:
1. First extracting facts from the document
2. Then analyzing risks, gaps, or inconsistencies from those facts
3. Preserving non-advisory boundaries
4. Producing a valid `TodoExecutionPlan`

{input_data_block}
