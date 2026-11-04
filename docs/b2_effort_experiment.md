# B2: model and effort experiment (2026-11-02)

Purpose: choose the (model, effort) arm for B2 by dev quality. This supersedes the model/effort choice in docs/d3_llm_decision.md once the outcome is recorded there as a dated amendment. Test pool untouched.

## Arms run on the 50 dev synsets (prompt v1, data/raw/llm/<tag>.jsonl)
| tag | model | effort | cost (50 prompts) |
|---|---|---|---|
| dev_v1 | claude-sonnet-5-5 | low | $0.0832 |
| dev_v1_medium | claude-sonnet-5-5 | medium | $0.0834 |
| (fill: high tag) | claude-sonnet-5-5 | high | (fill) |
| (fill: Opus tags) | claude-opus-5-5 | (fill) | (fill) |
Fill from the summary command. Output tokens were about 27 per prompt at low and medium.

## Rule (fixed before judging)
- Eligibility: projected project cost (llm_run --project) at or under cap_usd in configs/llm.json. Raising the cap needs a written owner decision.
- Quality: dev precision over all judged rows an arm proposed. Blind judging with docs/judging_guidelines.md. Rows already judged in the S4 sheet are reused; new rows go in data/eval/dev_judgments_b2.tsv.
- Choice: highest dev precision wins. Every arm within 5 points of the best counts as tied; among tied arms take the lowest projected cost, then the lower effort.
- Reported, not decisive: dev synsets with at least one correct candidate; distinct correct lemmas.
- No change to this rule after judging starts; a change needs a dated amendment made before the affected results are inspected.

## Disclosures
- Before this rule was fixed, the owner saw a listing of 10 of the 23 synsets where low and medium differed and noted one variant error (силау, medium).
- Owner's view: the differences between runs are mostly sampling noise (these models have no temperature setting). No repeat run of the same arm was made to measure it.
- Effort trials count toward the spend meter, so they eat into the $4 cap.
## Results (2026-11-02, dev set; data/reports/llm_dev_score.json)
Per arm over all judged rows it proposed; 0 rows excluded; Wilson 95%.
| arm | effort | judged | correct | precision | Wilson | dev synsets with a correct candidate | projected project cost |
|---|---|---|---|---|---|---|---|
| llm_dev_v1 | low | 126 | 92 | 0.730 | 0.647-0.800 | 45 | $1.37 |
| llm_dev_v1_medium | medium | 124 | 97 | 0.782 | 0.702-0.846 | 46 | $1.38 |
| llm_dev_v1_high | high | 128 | 102 | 0.797 | 0.719-0.857 | 45 | $1.45 |
Errors (wrong_sense / form / other / russian_loan / calque): low 19/7/4/3/1; medium 17/2/4/3/1; high 13/5/4/3/1.
Opus 5.5 arms were not run.

Rule outcome: best 0.797 (high). High and medium are within 5 points (1.5 points); low is 6.7 points behind. The tie-break (lowest projected cost, then lower effort) selects medium.

## Decision (owner, 2026-11-02)
The owner chose high effort. This deviates from the pre-registered tie-break and was decided after seeing the results, so it is a post-hoc deviation, not an amendment. Her reason: the cost difference is small (about $0.07 on the projected project cost) and high had the highest dev precision. The Wilson intervals of high and medium overlap almost entirely, so the dev data do not show that high is better.
Chosen arm: claude-sonnet-5-5, effort high, prompt v1.
