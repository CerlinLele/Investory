Task:
Classify an investment-related document into exactly one document type for the v0 review flow.

Context:
- This router only classifies the document type.
- Policy, missing-input, and safety checks may run outside this router.
- The router must not review document quality or answer the user.

Available document types:
- `etf_factsheet`
- `fund_prospectus`
- `product_brochure`
- `earnings_report`
- `learning_material`
- `unknown`

Rules:
- Use only the provided `document_excerpt`, `document_type_hint`, and `review_goal`.
- Prefer the document content over the hint when they conflict.
- If the material is unclear, mixed, or too weak to classify confidently, return `unknown`.
- Do not generate investment advice, buy/sell guidance, realtime analysis, or predictions.

Return one structured result:
- `document_type`: one available document type.
- `confidence`: number from `0.0` to `1.0`.
- `reason`: brief explanation for the classification.
- `missing_fields`: fields needed from the user when the type cannot be determined confidently.

Input:
{input_data_block}
