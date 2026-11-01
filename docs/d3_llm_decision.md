# D3: B2 LLM decision (2026-11-01)

Provider: Anthropic Claude API. Chosen by the owner.
Model choice delegated by the owner to the assistant (Claude) with a budget constraint. The assistant is made by the same provider; conflict of interest disclosed. Facts taken from Anthropic's pricing, deprecation, model-ID and migration pages.

## Choice
- Primary: claude-sonnet-5-5, effort low, structured (schema-constrained) JSON output, frozen prompt, every prompt and response logged.
- Fallback: claude-haiku-5-5, used only if the cost pilot projects more than the planned spend.
- Rejected: claude-opus-5-5 (projected cost above the budget; no evidence it is needed), claude-haiku-4-5-20251001 (retirement floor already passed; temperature needs the old API version).

## Budget
- Owner has $5 API credits and wants to stay within them. An extra $5 only if really necessary, with her written approval.
- Planned spend cap: $4.00. Console spend limit set to match.
- Rule fixed before any pilot output: projected cost = measured cost per prompt x (400 + 0.5 x 850). Sonnet 5.5 if <= $4.00, otherwise Haiku 5.5. Cost only, never quality.

## Criteria
| # | Criterion | Status |
|---|---|---|
| 1 | Kazakh lexical quality | Untested; judged on dev only |
| 2 | Independence | Not NLLB-based; may have seen Wiktionary (caveat for writeup) |
| 3 | Reproducibility | Pinned snapshot ID; no temperature on 5.5 models; fixed effort, structured output, frozen and hashed prompt, full logs |
| 4 | Output terms | Anthropic: customer owns outputs; dataset release allowed; competing-model use barred |
| 5 | Availability | Owner has API credits; Kazakhstan on the supported-countries list per the earlier report (not re-verified) |
| 6 | Cost | See Budget |
| 7 | Rate limits | Not checked; about 1,500 prompts is small |
| 8 | Key handling | ANTHROPIC_API_KEY env var or git-ignored file; never in repo or chat |
| 9 | Memorization risk | Model may have seen Wiktionary; list as writeup caveat |

## Not verified
- Sonnet 5.5 always-on thinking and effort levels (from OpenRouter notes, not Anthropic's page).
- Real token counts for Kazakh prompts and outputs (the pilot measures them).
- Output quality in Kazakh.
- Kazakhstan payment and availability.

Changes to model, effort, budget or the fallback rule need a dated amendment made before the affected outputs are inspected.
