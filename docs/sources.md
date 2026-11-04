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

## MT engine frozen for B1 (S4.5, 2026-10-31)
- engine: tilmash (issai/tilmash); chosen by rule higher_dev_precision on dev (tilmash 0.687 vs nllb600m 0.570)
- license: CC BY 4.0 as stated by the owner; fine-tuned from an NLLB-family model, so upstream NC terms unresolved
- decoding: beam search 4, no sampling (single Hugging Face adapter)
- run metadata (data/raw/mt/tilmash.meta.json): {"date": "2026-10-31", "device": "cpu", "do_sample": false, "engine": "tilmash", "family": "nllb", "max_new_tokens": 128, "model_id": "issai/tilmash", "num_beams": 4, "pools": ["dev", "rest", "test"], "python": "3.14.6", "resolved_revision": null, "src": "eng_Latn", "tgt": "kaz_Cyrl", "torch": "2.15.0", "transformers": "5.22.1"}

## LLM source for B2 frozen (2026-11-04)
- model: claude-sonnet-5-5 (Anthropic API), effort high, structured JSON output, max_tokens 3000, no sampling parameters
- prompt: prompts/b2_prompt_v1.txt, sha256 21708524d6fbf4e73a0d983e1239d01ff5c39e8379467dde2d861e71e02097a5
- run tags: dev_v1_high, rest_v1, test_v1; cost of these runs $1.7216
- not deterministic (no temperature control): data/raw/llm holds every prompt and response
- Anthropic's terms on using outputs in a published dataset: to be confirmed by the owner before release (D5)
