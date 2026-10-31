# Sources

## B0 dictionary: Wiktionary via kaikki.org (Wiktextract)
- Direction: English Wiktionary entries, Kazakh (kk) translation sections
- License: GFDL + CC BY-SA 4.0 (share-alike), as listed in the dictionary sheet; confirm on kaikki.org/Wiktionary before release. The released wordnet must be CC BY-SA 4.0 with attribution.
- Attribution: Wiktionary contributors, via Wiktextract / kaikki.org. Data was filtered, normalized and linked to WordNet synsets (modified).
- Dump: https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz
- File: raw-wiktextract-data.jsonl.gz (3082185963 bytes)
- sha256: 784574cc577d333bbf9e659be38efa27e75e9bfc0a2a8c7ab2371bb5fec29b2d
- Downloaded: 2026-10-30
- Dump version: enwiktionary dump dated 2026-10-01 (Wiktextract raw data)
- Cite: Tatu Ylonen, "Wiktextract: Wiktionary as Machine-Readable Structured Data", LREC 2022, pp. 1317-1325.

## How B0 uses it
- Role: B0 baseline, sense-blind. Wiktionary sense labels are NOT used in B0.
- POS-aware: WordNet n -> Wiktionary noun/name, v -> verb, a/s -> adj, r -> adv.
- Lookup: exact English lemma match, underscores replaced by spaces.
- Derived file: data/raw/en_kk_extract.jsonl (kk translations of the 1,000 scoped synsets' lemmas; CC BY-SA).
- Evidence format: {"dict": "kaikki", "entry_id": "<word>#<pos>@L<dump line>", "dump": "2026-10-01"}
- Measured coverage (data/reports/b0_coverage.json): 65.6% strict on 1,000 synsets (n 76.0%, a 52.2%, v 40.3%).

## MT engines: license notes (2026-10-31)
- tilmash (issai/tilmash): stated as CC BY 4.0; fine-tuned from an NLLB-family model, so the upstream terms are unresolved. Treated as permissive for the S4 tie rule only.
- nllb600m (facebook/nllb-200-distilled-600M): CC-BY-NC. Not treated as permissive.
- The final engine's model id, resolved revision, license and decoding settings are added at S4.5.