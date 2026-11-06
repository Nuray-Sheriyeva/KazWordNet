# S8 test judging protocol (decided before any test row was judged)

Timestamp: the git commit date of this file. The systems are frozen (`configs/systems_freeze.json`, tag `systems-v1`).

## Scope (option A)
- Test split: 100 synsets. One sheet row per (synset, lemma) pair proposed by any system (B1 union B2; B0 and B3 are subsets of these).
- Rest pool (about 850 synsets): not judged, except the D10 QC sample (25-30 random B3 rows from the rest pool, owner only, blind, same guidelines, reported separately with a Wilson interval, never part of the gate).
- Dev (50 synsets) is already judged by the owner alone and is not re-judged.

## Judges and order (D4, D11 revised, D13)
1. The owner judges every test row on her own sheet. A native Kazakh speaker who knows English (the checker, volunteer) judges the same rows on a separate sheet. The checker covers as many rows as they can; there is no quota. Rows are in a seeded order within synset, so any partial coverage is a random subset.
2. Neither judge sees the other's labels, the sources or the systems (key file closed until judging is finished). They do not discuss rows until both have finished.
3. Rows where the two first-pass labels differ, or where either is blank with an `UNSURE:` note, go to a new blank sheet for a third judge. The third judge sees POS, gloss and lemma only (no labels, no sources).
4. A label held by at least 2 of the 3 judges is final. If no label has 2 votes (for example the third judge also marks UNSURE), the owner, the checker and the third judge decide together; the outcome is recorded in a resolutions file. If they cannot decide, the row is recorded as `unresolved`.
5. Rows judged only by the owner (not reached by the checker) keep the owner's label.
6. Precision with unresolved rows is reported three ways: excluded, all counted correct, all counted incorrect. The gate uses the excluded version and the report states the range.

## Agreement (D12)
- Cohen's kappa and raw agreement are computed on the first-pass labels of rows both judged 0 or 1, before any third judge or discussion. Rows with UNSURE are excluded from kappa and counted. Adjudicated labels are never used for kappa.
- Report: rows both judged, raw agreement, kappa, number sent to the third judge, number unresolved.
- Sensitivity check: precision per system using the owner's labels alone.

## Judging rules
`docs/judging_guidelines.md` including the clarifications recorded on 2026-10-31. Unchanged for test.