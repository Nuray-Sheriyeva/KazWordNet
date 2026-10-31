"""S4.5: build the final data/candidates/mt.tsv (+ mt_rejected.tsv) from the engine chosen on dev.

The engine is read from data/reports/mt_dev_score.json (decision.winner), never typed by hand.
Run after: mt_run --pools dev,rest,test --allow-test, then mt_parse --engine <engine>.
"""
import argparse
import json
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

from kazwn import candidates as C

ROOT = Path(__file__).resolve().parents[2]
SCORE = ROOT / "data/reports/mt_dev_score.json"
CAND = ROOT / "data/candidates"
RAW = ROOT / "data/raw/mt"
SOURCES_MD = ROOT / "docs/sources.md"
MODEL_ID = {"tilmash": "issai/tilmash", "nllb600m": "facebook/nllb-200-distilled-600M"}
LICENSE = {
    "tilmash": "CC BY 4.0 as stated by the owner; fine-tuned from an NLLB-family model, so upstream NC terms unresolved",
    "nllb600m": "CC-BY-NC",
}


def chosen(score_path=SCORE):
    rep = json.loads(Path(score_path).read_text(encoding="utf-8"))
    winner = rep["decision"]["winner"]
    if not winner:
        raise SystemExit("no winner recorded in mt_dev_score.json (unresolved tie): decide with the owner")
    return winner, rep


def convert(engine, cand_dir=CAND):
    cand_dir = Path(cand_dir)
    cands = [replace(c, source="mt") for c in C.read_candidates(cand_dir / f"mt_{engine}.tsv")]
    rejs = [replace(r, source="mt") for r in C.read_rejected(cand_dir / f"mt_{engine}_rejected.tsv")]
    C.write_candidates("mt", cands, cand_dir / "mt.tsv")
    C.write_rejected("mt", rejs, cand_dir / "mt_rejected.tsv")
    return len(cands), len(rejs), len({c.synset_id for c in cands})


def sources_block(engine, rep, meta):
    d = rep["decision"]
    pa, pb = d["dev_precision"][d["finalists"][0]], d["dev_precision"][d["finalists"][1]]
    return (
        f"\n## MT engine frozen for B1 (S4.5, {date.today().isoformat()})\n"
        f"- engine: {engine} ({MODEL_ID.get(engine, '?')}); chosen by rule {d['rule']} on dev "
        f"({d['finalists'][0]} {pa:.3f} vs {d['finalists'][1]} {pb:.3f})\n"
        f"- license: {LICENSE.get(engine, '?')}\n"
        f"- decoding: beam search 4, no sampling (single Hugging Face adapter)\n"
        f"- run metadata (data/raw/mt/{engine}.meta.json): {json.dumps(meta, ensure_ascii=False, sort_keys=True)}\n"
    )


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-sources", action="store_true", help="append the frozen-engine block to docs/sources.md")
    args = ap.parse_args(argv)
    engine, rep = chosen()
    n, nr, ns = convert(engine)
    print(f"engine {engine}: mt.tsv {n} rows over {ns} synsets; mt_rejected.tsv {nr} rows")
    meta = json.loads((RAW / f"{engine}.meta.json").read_text(encoding="utf-8"))
    block = sources_block(engine, rep, meta)
    print(block)
    if args.write_sources:
        text = SOURCES_MD.read_text(encoding="utf-8")
        if "## MT engine frozen for B1" in text:
            print("docs/sources.md already has the frozen-engine block; not appended")
        else:
            SOURCES_MD.write_text(text.rstrip("\n") + "\n" + block, encoding="utf-8")
            print("appended to docs/sources.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())