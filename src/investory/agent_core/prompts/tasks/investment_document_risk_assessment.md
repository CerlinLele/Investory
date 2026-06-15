Task:
Assess overall risk and approval disposition for a completed investment document review.

Requirements:
{common_rules}
- Use only the provided `document_type`, `route_confidence`, `risk_findings`, `information_gaps`, `boundary_notes`, and `task_status_summary`.
- Treat the input as structured review evidence; do not ask for or rely on the full document text.
- Do not invent facts, findings, or task outcomes that are not present in the input.
- Do not give buy, sell, hold, timing, suitability, allocation, or return-prediction advice.
- Determine a machine-readable `overall_risk` of `low`, `medium`, or `high`.
- Set `approval_status` to match the risk assessment outcome rather than rewriting the review report.
- `high` risk must include one or more `critical_issues`.
- `low` and `medium` risk should default to `auto_proceed=true`.
- `high` risk should default to `auto_proceed=false`.
- If the evidence is incomplete because tasks failed, were skipped, or key information is missing, reflect that in `risk_reason`, `critical_issues`, or both.
- Keep the result concise, auditable, and grounded in the provided structured evidence.

Focus on:
1. Overall risk level
2. Risk reason grounded in the structured findings
3. Critical issues that block automatic downstream release
4. Approval status and required role when human review is needed
5. Auto-proceed decision

{input_data_block}
