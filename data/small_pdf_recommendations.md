# Small PDF Recommendations

These smaller official PDFs are good candidates for daily document-review tests.

| PDF | Source | Pages | Good For | document_type_hint |
|---|---|---:|---|---|
| [HYG iShares High Yield Corporate Bond ETF Fact Sheet](https://www.ishares.com/us/literature/fact-sheet/hyg-ishares-iboxx-high-yield-corporate-bond-etf-fund-fact-sheet-en-us.pdf) | iShares / BlackRock | 3 | Lightweight smoke test, bond ETF, credit risk, yield disclosure | `etf_factsheet` |
| [IVV iShares Core S&P 500 ETF Fact Sheet](https://www.ishares.com/us/literature/fact-sheet/ivv-ishares-core-s-p-500-etf-fund-fact-sheet-en-us.pdf) | iShares / BlackRock | 4 | Standard equity ETF factsheet, fees, holdings, sector allocation | `etf_factsheet` |
| [IJR iShares Core S&P Small-Cap ETF Fact Sheet](https://www.ishares.com/us/literature/fact-sheet/ijr-ishares-core-s-p-small-cap-etf-fund-fact-sheet-en-us.pdf) | iShares / BlackRock | 4 | Small-cap ETF, risk disclosure, volatility language | `etf_factsheet` |
| [TLT iShares 20+ Year Treasury Bond ETF Fact Sheet](https://www.ishares.com/us/literature/fact-sheet/tlt-ishares-20-year-treasury-bond-etf-fund-fact-sheet-en-us.pdf) | iShares / BlackRock | 4 | Duration risk, rate sensitivity, bond exposure | `etf_factsheet` |
| [EFA iShares MSCI EAFE ETF Fact Sheet](https://www.ishares.com/us/literature/fact-sheet/efa-ishares-msci-eafe-etf-fund-fact-sheet-en-us.pdf) | iShares / BlackRock | 4 | International ETF, country and sector allocation | `etf_factsheet` |
| [IEMG iShares Core MSCI Emerging Markets ETF Fact Sheet](https://www.ishares.com/us/literature/fact-sheet/iemg-ishares-core-msci-emerging-markets-etf-fund-fact-sheet-en-us.pdf) | iShares / BlackRock | 4 | Emerging markets ETF, concentration and country risk | `etf_factsheet` |

Recommended starting points:

- `HYG` for the fastest smoke test
- `IVV` for the most standard ETF-factsheet structure

Suggested local storage layout:

```text
data/pdfs/hyg_fact_sheet.pdf
data/pdfs/ivv_fact_sheet.pdf
```

Suggested review goal:

```text
Review fee clarity, risk disclosure, holdings, and performance limitations
```
