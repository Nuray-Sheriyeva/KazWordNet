# S4 engine selection rule

Fixed before any engine output is inspected.

- Pool: dev + rest synsets only (the 900 scoped synsets not in eval_test). The test pool is never run until the engine is frozen.
- Engines compared: tilmash, nllb600m, m2m100.
- Eligible: parse_ok / raw_rows >= 0.70 and at least 0.90 of parsed headwords survive S1.
- Ranking among eligible engines: (1) B0 hit rate, i.e. the share of B0-covered synsets for which MT proposes >= 1 B0 candidate; (2) incremental coverage, i.e. B0-uncovered synsets that get >= 1 valid MT candidate.
- Finalists: top 2. The native-speaker judge (dev set, 50 synsets) marks each MT candidate correct/incorrect. Final pick = higher dev precision; if within 5 points, prefer the permissively licensed engine; if still tied, higher incremental coverage.
- The chosen engine, its model id, resolved revision, license and decoding settings are recorded in docs/sources.md.

## Amendment (2026-10-30, before any full engine run)
m2m100 is dropped after the 5-input smoke test: outputs were degenerate repetition with no `headword:` structure, so it would fail the parse-success eligibility threshold. The smoke output is kept as evidence (data/raw/mt/m2m100.smoke.jsonl). Remaining engines: tilmash, nllb600m.


## Amendment (2026-10-31, before any per-engine dev precision was computed)
Interpretation of "permissively licensed" in the tie rule. Dev judging is finished, but no per-engine precision has been computed yet. tilmash is treated as permissively licensed: its license was found to be stated as CC BY 4.0. nllb600m is not: its weights are CC-BY-NC. Caveat: tilmash is fine-tuned from an NLLB-family model, so whether the upstream non-commercial restriction carries over is unresolved, and the statement has not yet been checked against the issai/tilmash model card. This interpretation applies to the tie-break only. The release license and whether MT-derived lemmas are released are decided separately (D5).