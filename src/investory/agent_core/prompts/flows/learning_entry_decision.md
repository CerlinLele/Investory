Task:
Decide whether the current request is asking for direct investment advice.

Context:
- Missing-field detection has already happened before this step.
- Task type mapping is handled elsewhere.
- This step only decides whether the request should be refused and redirected, or allowed to continue as a learning task.

Return one structured result:

- `route_action`: use `refuse_and_redirect` if the request asks for buying, selling, timing, personalized allocation, or other direct investment decision guidance. Use `execute_learning_task` if the request is educational, explanatory, summarization-focused, or asks for a learning-oriented brief.
- `reason`: briefly explain the classification.

Do not:
- Ask for missing fields.
- Select qa, summary, or brief.
- Generate the final user-facing answer.
- Provide investment advice.

Input:
{input_data_block}
