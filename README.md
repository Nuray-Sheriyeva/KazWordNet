# KazWordNet

A small, evaluated **Kazakh WordNet**, built by automatic methods as a mini-replication of published wordnet-construction work. Synsets from Princeton WordNet 3.0 are given Kazakh lemmas by several systems, and the systems are compared by precision and coverage against judgments from a native Kazakh speaker.

## Scope

- **1,000 synsets** sampled from Core WordNet (4,953 resolved synsets; nouns, verbs and adjectives, no adverbs in the list). The Core list has no ranking, so the sample is a seeded, POS-proportional random sample.
- **Evaluation set:** 150 POS-stratified synsets, split into **50 dev** (for tuning) and **100 test** (judged once).
- **5,000 synsets** only if a pre-registered gate passes on the test set (precision, Wilson lower bound, coverage and per-POS precision thresholds in `configs/gate.json`).

## Systems

| System | Description | Status |
|---|---|---|
| B0 | Dictionary only: Wiktionary translations via kaikki.org, POS-aware, sense-blind | done |
| B1 | B0 plus gloss-aware machine translation (`lemma: gloss`) | done |
| B2 | LLM prompted with gloss, examples and hypernym | done |
| B3 | Keep lemmas that at least 2 of 3 sources agree on (dictionary, MT, LLM) | done (dev preview) |

The MT engine was chosen between Tilmash and NLLB-200-600M by a rule fixed before the results (`docs/s4_selection_rule.md`).

## Main features

- **Reproducible and leak-safe:** scope and eval splits are frozen, hashed and read-only; the gate, the engine selection rule and the judging guidelines were written before any results; the test pool is blocked in code unless `--allow-test`.
- **Shared candidate format** (`src/kazwn/candidates.py`): every source writes the same TSV with provenance (dictionary entry or raw MT output) and flags; rejected strings are logged, not dropped.
- **Kazakh text normalizer:** strict 42-letter Cyrillic check, Latin/Cyrillic look-alike repair, verb citation form check (-у/-ю), hints for loan letters.
- **Blind judging workflow:** one sheet row per (synset, lemma), source hidden, error categories (`wrong_sense`, `calque`, `russian_loan`, `variant`, `form`, `other`).
- **Verification scripts** for every stage; each ends in `ALL CHECKS PASSED` or lists failures.

## Results so far (dev set, preliminary: 50 synsets, one judge)

- B0 coverage on the 1,000 synsets: 65.6% (nouns 76.0%, adjectives 52.2%, verbs 40.3%).
- B0 dev precision: 0.750.
- MT engine selection on dev precision: Tilmash 0.687 vs NLLB-200-600M 0.570.
- B1 (B0 plus Tilmash MT) is a union of two scored sources, so it has no separate dev figure; its precision is reported with the test evaluation. Tilmash proposes at least one candidate for 981 of the 1,000 synsets.
- B2 (Claude Sonnet 5.5, prompt v1) dev precision by reasoning effort: low 0.730, medium 0.782, high 0.797. High effort was used, chosen after seeing the results (the pre-registered tie-break would have picked medium).
- B2 proposes at least one candidate for 989 of the 1,000 synsets.
- B3 (2-of-3 vote, exact match after normalization) dev precision 0.900 (54/60; Wilson 0.799-0.953), 40 of 50 dev synsets have a candidate (coverage 0.80). Dev precision of the other systems: B0 0.750, MT (Tilmash) 0.687, B1 0.675, B2 0.797. The vote rule was fixed before these results. The B3 figures are a non-binding preview on 50 dev synsets with one judge; per-POS counts are small (verbs 7/8, adjectives 6/7 judged correct); the pre-registered gate is applied to the test split only.

## Repository layout

```
configs/    gate.json, mt_engines.json
docs/       sources.md, s4_selection_rule.md, judging_guidelines.md
src/kazwn/  scope, sampling, freezing, eval split, gate; candidates, kaikki, B0; MT inputs/run/parse/selection; judging sheet; verify_*.py
tests/      pytest tests
data/       raw/, scope/, eval/, candidates/, reports/
```

## Running

```bash
pip install -r requirements.txt            # MT stage also needs requirements-mt.txt
PYTHONPATH=src python -m pytest tests -q
PYTHONPATH=src python -m kazwn.verify_scope   # also verify_freeze, verify_split, verify_b0, verify_mt
```

Modules run as `PYTHONPATH=src python -m kazwn.<module>`. The 3 GB Wiktionary dump is not in the repo (`data/dumps/` is git-ignored); see `docs/sources.md` for its source, date and checksum.

## Data and licenses

- **Princeton WordNet 3.0:** see the [WordNet license](https://wordnet.princeton.edu/license-and-commercial-use).
- **Wiktionary** (via kaikki.org / Wiktextract): GFDL and CC BY-SA 4.0, share-alike. Derived Kazakh lemmas are therefore planned for release under **CC BY-SA 4.0**.
- **MT models:** terms are recorded in `docs/sources.md`.

## Limitations

Single judge; small dev sample; no adverbs in the scope; gate thresholds are the author's choices informed by published results, not a standard.

## Citation

Ylonen, T. (2022). Wiktextract: Wiktionary as Machine-Readable Structured Data. *Proceedings of LREC 2022*, pp. 1317-1325.
