"""Recompute every number in data/reports/llm_dev_score.json from the raw sheets and raw LLM logs."""
import csv
import json
import sys

from kazwn import llm_dev_score as S
from kazwn import llm_run as L
from kazwn import mt_dev_score as M

TOL = 1e-9


def tsv(path, enc):
    return list(csv.DictReader(open(path, encoding=enc, newline=""), delimiter="\t"))


def main():
    fails = []
    rep = json.loads(S.OUT.read_text(encoding="utf-8"))
    cfg = L.load_cfg()
    test_ids = M.read_ids(M.TEST)
    s4 = {r["key_id"]: r for r in tsv(M.SHEET, "utf-8-sig")}
    b2 = {r["key_id"]: r for r in tsv(S.B2_SHEET, "utf-8-sig")}
    key = {r["key_id"]: r for r in tsv(S.B2_KEY, "utf-8-sig")}
    if set(s4) & set(b2):
        fails.append("rows judged in both sheets")
    if any(r["synset_id"] in test_ids for r in list(s4.values()) + list(b2.values())):
        fails.append("test-pool synsets in a sheet")
    if {k for k, v in key.items() if v["in_s4_sheet"] == "0"} != set(b2):
        fails.append("B2 sheet rows differ from the key's in_s4_sheet=0 rows")
    if not {k for k, v in key.items() if v["in_s4_sheet"] == "1"} <= set(s4):
        fails.append("key rows marked in_s4_sheet=1 missing from the S4 sheet")
    judged = lambda kid: (s4.get(kid) or b2[kid])["correct"].strip()
    if len(key) != rep["judged_rows"]:
        fails.append("row count differs from report")
    for arm, v in rep["arms"].items():
        mine = [kid for kid, k in key.items() if arm in k["sources"].split("|")]
        j = [kid for kid in mine if judged(kid) in ("0", "1")]
        k_ok = sum(judged(kid) == "1" for kid in j)
        checks = {"proposed": (len(mine), v["proposed"]), "judged": (len(j), v["judged"]),
                  "correct": (k_ok, v["correct"]), "excluded_blank": (len(mine) - len(j), v["excluded_blank"]),
                  "synsets_with_correct": (len({kid.split("|")[0] for kid in j if judged(kid) == "1"}), v["dev_synsets_with_correct"])}
        for name, (a, b) in checks.items():
            if a != b:
                fails.append(f"{arm}: {name} recomputed {a} != reported {b}")
        if j and abs(k_ok / len(j) - v["precision"]) > TOL:
            fails.append(f"{arm}: precision mismatch")
        raw = L.read_raw(L.RAW / f"{arm[len('llm_'):]}.jsonl")
        mean = sum(r["cost_usd"] for r in raw) / len(raw)
        p = cfg["projection"]
        if abs(mean * (p["standard_prompts"] + p["batch_prompts"] * p["batch_discount"]) - v["projected_total_usd"]) > TOL:
            fails.append(f"{arm}: projected cost does not recompute")
        if {r["effort"] for r in raw} != {v["effort"]} or {r["model"] for r in raw} != {v["model"]}:
            fails.append(f"{arm}: model/effort differ from the raw log")
    prec = {a: v["precision"] for a, v in rep["arms"].items()}
    cost = {a: v["projected_total_usd"] for a, v in rep["arms"].items()}
    elig = [a for a in prec if cost[a] <= cfg["cap_usd"]]
    best = max(prec[a] for a in elig)
    tied = sorted(a for a in elig if (best - prec[a]) * 100 <= 5.0 + 1e-6)
    if tied != rep["decision"]["tied"]:
        fails.append(f"tied set {tied} != reported {rep['decision']['tied']}")
    if fails:
        print("FAILED:")
        for f in fails:
            print(" -", f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())