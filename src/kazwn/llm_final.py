"""B2: assemble the final data/candidates/llm.tsv (+ llm_rejected.tsv) from the frozen run tags.

Usage: PYTHONPATH=src python -m kazwn.llm_final --tags dev_v1_high,rest_v1,test_v1 [--write-sources]
The tags together must cover every scoped synset exactly once, all with the frozen prompt, model and effort.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from kazwn import llm_run as L
from kazwn.candidates import CAND_DIR, read_candidates, read_rejected, write_candidates, write_rejected

SOURCES_MD = L.ROOT / "docs/sources.md"


def check_runs(tags, scope_ids, freeze_path=L.FREEZE, raw_dir=L.RAW):
    """Consistency of the raw logs with the freeze file and the scope. Returns a list of problems."""
    fz = json.loads(Path(freeze_path).read_text(encoding="utf-8"))
    problems, ids = [], []
    for t in tags:
        rows = L.read_raw(Path(raw_dir) / f"{t}.jsonl")
        if not rows:
            problems.append(f"{t}: no raw rows")
        for r in rows:
            ids.append(r["input_id"])
            if (r["model"], r["effort"], r["prompt_sha256"]) != (fz["model"], fz["effort"], fz["prompt_sha256"]):
                problems.append(f"{t}: {r['input_id']} not run with the frozen model/effort/prompt")
                break
    if len(ids) != len(set(ids)):
        problems.append("a synset appears in more than one tag")
    if set(ids) != set(scope_ids):
        problems.append(f"tags cover {len(set(ids) & set(scope_ids))} of {len(scope_ids)} scoped synsets; "
                        f"{len(set(ids) - set(scope_ids))} outside the scope")
    return problems


def missing_files(tags, cand_dir=CAND_DIR, final=False):
    """Parsed per-tag candidate files (and optionally the final llm files) that do not exist yet."""
    cand_dir = Path(cand_dir)
    names = [f"llm_{t}{k}.tsv" for t in tags for k in ("", "_rejected")]
    if final:
        names += ["llm.tsv", "llm_rejected.tsv"]
    return [n for n in names if not (cand_dir / n).exists()]


def convert(tags, cand_dir=CAND_DIR):
    cand_dir = Path(cand_dir)
    cands = [c for t in tags for c in read_candidates(cand_dir / f"llm_{t}.tsv")]
    rejs = [r for t in tags for r in read_rejected(cand_dir / f"llm_{t}_rejected.tsv")]
    merged = write_candidates("llm", cands, cand_dir / "llm.tsv")
    write_rejected("llm", rejs, cand_dir / "llm_rejected.tsv")
    return len(merged), len(rejs), len({c.synset_id for c in merged})


def sources_block(tags, fz, cost):
    return (
        f"\n## LLM source for B2 frozen ({date.today().isoformat()})\n"
        f"- model: {fz['model']} (Anthropic API), effort {fz['effort']}, structured JSON output, "
        f"max_tokens {fz['max_tokens']}, no sampling parameters\n"
        f"- prompt: {fz['prompt_file']}, sha256 {fz['prompt_sha256']}\n"
        f"- run tags: {', '.join(tags)}; cost of these runs ${cost:.4f}\n"
        f"- not deterministic (no temperature control): data/raw/llm holds every prompt and response\n"
        f"- Anthropic's terms on using outputs in a published dataset: to be confirmed by the owner before release (D5)\n"
    )


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", required=True)
    ap.add_argument("--write-sources", action="store_true")
    a = ap.parse_args(argv)
    tags = a.tags.split(",")
    scope = {r["synset_id"] for r in L.read_tsv(L.SCOPE)}
    problems = check_runs(tags, scope)
    if problems:
        print("FAILED:")
        for p in problems:
            print(" -", p)
        return 1
    missing = missing_files(tags)
    if missing:
        print("FAILED: run llm_parse for these tags first; missing " + ", ".join(missing))
        return 1
    n, nr, ns = convert(tags)
    print(f"llm.tsv {n} rows over {ns} synsets; llm_rejected.tsv {nr} rows")
    fz = json.loads(L.FREEZE.read_text(encoding="utf-8"))
    cost = sum(r["cost_usd"] for t in tags for r in L.read_raw(L.RAW / f"{t}.jsonl"))
    block = sources_block(tags, fz, cost)
    print(block)
    if a.write_sources:
        text = SOURCES_MD.read_text(encoding="utf-8")
        if "## LLM source for B2 frozen" in text:
            print("docs/sources.md already has the LLM block; not appended")
        else:
            SOURCES_MD.write_text(text.rstrip("\n") + "\n" + block, encoding="utf-8")
            print("appended to docs/sources.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())