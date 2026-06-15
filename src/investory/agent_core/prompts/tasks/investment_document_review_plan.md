Task:
Generate a structured To-Do plan for reviewing the investment-related document.

Requirements:
{common_rules}
- Use only the provided `document_text`, `document_type`, `extract_focus`, `analyze_focus`, and optional `review_goal`.
- Keep the plan within investment document review boundaries; do not create buy, sell, hold, timing, suitability, allocation, return-prediction, real-time market data, or personalized advice tasks.
- Create stable, short task ids in lowercase snake_case, such as `extract_fees`, `extract_holdings`, or `analyze_fee_disclosure`.
- Task ids must be unique and must not change between retries for the same document and focus.
- Prefer 4 to 8 total tasks for long documents; keep shorter documents smaller.
- Use `investment_document_extract` for factual extraction tasks.
- Extract tasks must only extract document-grounded facts, source citations, and missing source details.
- Extract tasks must not judge risk, quality, suitability, performance, consistency, or disclosure adequacy.
- Extract tasks must use `depends_on=[]`.
- Use `investment_document_analyze` for analysis tasks.
- Analyze tasks must depend on at least one extract task.
- Analyze tasks must judge only from upstream extracted facts and must not invent raw facts from the document independently.
- Analyze tasks may assess risks, disclosure quality, information gaps, inconsistencies, or source limitations.
- Analyze task payloads must identify the relevant `analyze_focus` and the upstream fact areas they need.
- Every `depends_on` entry must reference an existing task id exactly; do not use unknown ids or self-dependencies.
- Every task must have a clear title, description, payload, and non-empty `completion_criteria`.
- Each `completion_criteria` item must be specific and checkable, not generic wording such as "task is complete".
- Use one to three `completion_criteria` items per task.
- The plan must not contain cycles; dependencies must flow from extract tasks to analyze tasks.
- The plan summary should explain the review strategy without making an investment recommendation.

Focus on:
1. First extracting facts from the document
2. Then analyzing risks, gaps, or inconsistencies from those facts
3. Preserving non-advisory boundaries
4. Producing a valid `TodoExecutionPlan`

{input_data_block}
