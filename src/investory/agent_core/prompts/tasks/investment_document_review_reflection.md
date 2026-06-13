Task:
Evaluate and optionally revise a completed investment document review result before risk assessment.

Requirements:
{common_rules}
- Use only the provided `document_type`, `route_confidence`, optional `review_goal`, `review_result`, optional To-Do context, `review_summary`, and `criteria`.
- Treat `review_result` as the current structured result and return the same external review structure inside `review_result`.
- Do not add facts, risks, task outcomes, or source details that are not present in the input.
- Do not change the output schema or introduce fields outside the reflection result contract.
- Do not give buy, sell, hold, timing, suitability, allocation, or return-prediction advice.
- If successful extract, analyze, or synthesize outputs support facts, preserve them in `extracted_facts`.
- If tasks failed, were skipped, or lacked evidence, reflect the limitation under `information_gaps` or `boundary_notes`.
- Keep `risk_findings` evidence-based and non-advisory.
- Keep `summary` concise, audit-friendly, and clear about key risks and limitations.
- Use `passed`, `score`, `issues`, `suggestions`, `safety_flags`, and `rounds` to make the reflection outcome observable.
- Respect `max_rounds`; if no revision is allowed or needed, return the original review result with the critique metadata.

Focus on:
1. Criteria compliance
2. Unsupported fact risk
3. Investment-advice boundary risk
4. Failed or skipped task disclosure
5. Concise revised review output
6. Observable reflection metadata

{input_data_block}
