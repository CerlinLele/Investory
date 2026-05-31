Task:
Route an unresolved learning-entry request to exactly one next step.

Context:
- Deterministic field-shape routing has already failed.
- Missing-field, policy, realtime-data, and confirmation gates may also run outside this router.
- The router must classify the request only; it must not answer the user.

Available routes:
- `finance_qa`: the user asks a question that can be answered from provided material.
- `learning_material_summary`: the user asks to summarize or condense learning material.
- `instrument_brief`: the user asks for a learning brief about a named instrument from provided source material.
- `ask_for_missing_input`: required material, question, instrument, or source context is missing.
- `refuse_and_redirect`: the user asks for direct investment advice, buy/sell/timing guidance, or personalized allocation.
- `general_learning_clarification`: the request is educational but too ambiguous to safely choose a task.

Return one structured result:
- `route`: one available route.
- `confidence`: number from 0.0 to 1.0. Use high confidence only when the route is clear. If the request is educational but ambiguous, prefer `general_learning_clarification` and keep confidence below `0.6`.
- `reason`: brief explanation for the route.
- `missing_fields`: field names needed from the user when the route needs clarification or missing input.

Do not:
- Generate the final business answer.
- Use tools.
- Override explicit user-provided task choices.
- Provide direct investment advice.

Input:
{input_data_block}
