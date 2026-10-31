"""Verifies S4.1-S4.3. Run: PYTHONPATH=src python -m kazwn.verify_mt [--allow-test]"""
import argparse, csv, json, re, sys
from collections import Counter

from kazwn.candidates import CAND_DIR, normalize, read_candidates, read_rejected, split_translations
from kazwn.kaikki import load_scope, scope_lemmas
from kazwn.mt_inputs import EVAL, OUT as INPUTS, read_ids
from kazwn.mt_parse import MT_DIR, REPORTS, extract_head, read_raw

ap = argparse.ArgumentParser()
ap.add_argument("--allow-test", action="store_true")
ALLOW_TEST = ap.parse_args().allow_test
fails = []


def check(name, ok, detail=""):
    print("PASS" if ok else "FAIL", "-", name, detail)
    if not ok:
        fails.append(name)


# ---- S4.1 inputs
with open(INPUTS, encoding="utf-8", newline="") as f:
    inputs = list(csv.DictReader(f, delimiter="\t"))
by_id = {r["input_id"]: r for r in inputs}
scope = load_scope()
dev_ids, test_ids = read_ids(EVAL / "eval_dev.tsv"), read_ids(EVAL / "eval_test.tsv")
check("input ids unique", len(by_id) == len(inputs))
check("one input per (synset, lemma)", len(inputs) == sum(len(scope_lemmas(r)) for r in scope), str(len(inputs)))
check("every scoped synset has an input", {r["synset_id"] for r in scope} == {i["synset_id"] for i in inputs})
gloss = {r["synset_id"]: r["gloss"] for r in scope}
check("text is 'lemma: gloss'", all(i["text"] == f"{i['lemma_en']}: {gloss[i['synset_id']]}" for i in inputs))
check("test pool == eval_test synsets", {i["synset_id"] for i in inputs if i["pool"] == "test"} == test_ids)
check("dev pool == eval_dev synsets", {i["synset_id"] for i in inputs if i["pool"] == "dev"} == dev_ids)

# ---- S4.2 raw outputs / S4.3 candidates, per engine
engines = sorted(p.stem for p in MT_DIR.glob("*.jsonl") if not p.name.endswith(".smoke.jsonl"))
check("at least one engine run", bool(engines), str(engines))
for eng in engines:
    print(f"\n== engine {eng}")
    raw = read_raw(MT_DIR / f"{eng}.jsonl")
    check(f"[{eng}] meta file with revision", (MT_DIR / f"{eng}.meta.json").exists()
          and "resolved_revision" in json.loads((MT_DIR / f"{eng}.meta.json").read_text(encoding="utf-8")))
    check(f"[{eng}] raw ids unique and known", len({r["input_id"] for r in raw}) == len(raw)
          and all(r["input_id"] in by_id for r in raw))
    check(f"[{eng}] input/pool match inputs file", all(by_id[r["input_id"]]["text"] == r["input"]
          and by_id[r["input_id"]]["pool"] == r["pool"] for r in raw))
    check(f"[{eng}] no test-pool rows (leak guard)", ALLOW_TEST or not any(r["pool"] == "test" for r in raw))
    check(f"[{eng}] outputs are strings", all(isinstance(r["output"], str) for r in raw))
    print("info: empty outputs:", sum(1 for r in raw if not r["output"].strip()), "of", len(raw))

    cpath, rpath = CAND_DIR / f"mt_{eng}.tsv", CAND_DIR / f"mt_{eng}_rejected.tsv"
    if not cpath.exists():
        print("info: not parsed yet (run kazwn.mt_parse)")
        continue
    cands, rejs = read_candidates(cpath), read_rejected(rpath)
    rep = json.loads((REPORTS / f"mt_parse_{eng}.json").read_text(encoding="utf-8"))
    raw_by_id = {r["input_id"]: re.sub(r"[\t\r\n]+", " ", r["output"]) for r in raw}
    keys = [(c.synset_id, c.lemma_kk, c.source) for c in cands]
    check(f"[{eng}] all source == mt, keys unique", all(c.source == "mt" for c in cands) and len(keys) == len(set(keys)))
    check(f"[{eng}] lemma_kk normalized", all(normalize(c.lemma_kk, c.pos).lemma == c.lemma_kk for c in cands))

    def traceable(c):
        for e in c.evidence:
            if e.get("engine") != eng or raw_by_id.get(e["input_id"]) != e["raw"]:
                return False
            head, _ = extract_head(e["raw"])
            if head is None or c.lemma_kk not in {n.lemma for p in split_translations(head)
                                                  for n in [normalize(p, c.pos)] if n.ok}:
                return False
        return bool(c.evidence)

    check(f"[{eng}] every candidate traces to raw output and its headword", all(traceable(c) for c in cands))
    fail_n = sum(rep["parse_fail"].values())
    check(f"[{eng}] report: parse_ok + parse_fail == raw rows", rep["parse_ok"] + fail_n == len(raw) == rep["raw_rows"])
    check(f"[{eng}] rejected rows == parse_fail + s1_rejected", len(rejs) == fail_n + sum(rep["s1_rejected"].values()))
    check(f"[{eng}] no test-pool candidates (leak guard)",
          ALLOW_TEST or not ({c.synset_id for c in cands} & test_ids))
    print("info: parse_fail", rep["parse_fail"], "| s1_rejected", rep["s1_rejected"],
          "| flags", rep["flags"], "| synsets with candidates", rep["synsets_with_candidates"])

print("\nALL CHECKS PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)