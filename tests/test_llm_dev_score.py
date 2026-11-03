import csv
from types import SimpleNamespace

import pytest

from kazwn import llm_dev_score as S
from kazwn import llm_run as L
from kazwn import mt_dev_score as M

CFG = L.load_cfg()


class Fake:
    def __init__(self, out_tokens):
        self.out = out_tokens
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kw):
        return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"lemmas": []}')],
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=self.out), stop_reason="end_turn")


def raw_log(raw_dir, tag, out_tokens, effort="low"):
    scope = [{"synset_id": f"x{i}", "pos": "n", "lemmas_en": "a", "gloss": "g", "examples": "", "hypernym_lemmas": ""} for i in range(2)]
    L.run(L.build_inputs(scope, {"x0", "x1"}, set()), {"dev"}, tag, "primary", dict(CFG, effort=effort),
          client=Fake(out_tokens), raw_dir=raw_dir, log=lambda *_: None)


def write_tsv(path, cols, rows, enc="utf-8", nl="\r\n"):
    with open(path, "w", encoding=enc, newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator=nl)
        w.writerow(cols)
        w.writerows([[r[c] for c in cols] for r in rows])


def make(tmp, arms, truth, in_s4=()):
    """arms {arm: [lemma]}, truth {lemma: 1/0}; lemmas in in_s4 sit in the S4 sheet, the rest in the B2 sheet."""
    lemmas = sorted({l for ls in arms.values() for l in ls})
    def row(l):
        sid = f"s{lemmas.index(l) // 2}"
        c = truth[l]
        return {"key_id": f"{sid}|{l}", "synset_id": sid, "pos": "n", "lemma_en": "en", "gloss": "g", "lemma_kk": l,
                "correct": str(c), "error_category": "" if c else "wrong_sense", "notes": ""}
    b0_only = {"key_id": "sb0|b0only", "synset_id": "sb0", "pos": "n", "lemma_en": "en", "gloss": "g", "lemma_kk": "b0only",
               "correct": "1", "error_category": "", "notes": ""}  # a B0-only row the arms never proposed: must be ignored
    s4_rows = [row(l) for l in lemmas if l in in_s4] + [b0_only]
    b2_rows = [row(l) for l in lemmas if l not in in_s4]
    s4_key = [{"key_id": r["key_id"], "sources": "b0_dict", "flags": ""} for r in s4_rows]
    b2_key = [{"key_id": row(l)["key_id"], "sources": "|".join(sorted(a for a, ls in arms.items() if l in ls)),
               "flags": "", "in_s4_sheet": "1" if l in in_s4 else "0"} for l in lemmas]
    p = {"s4_sheet": tmp / "s4.tsv", "s4_key": tmp / "s4k.tsv", "b2_sheet": tmp / "b2.tsv", "b2_key": tmp / "b2k.tsv"}
    write_tsv(p["s4_sheet"], M.SHEET_COLS, s4_rows, "utf-8-sig")
    write_tsv(p["s4_key"], M.KEY_COLS, s4_key)
    write_tsv(p["b2_sheet"], M.SHEET_COLS, b2_rows, "utf-8-sig")
    write_tsv(p["b2_key"], S.KEY_COLS, b2_key)
    return p


def lem(prefix, n):
    return [f"{prefix}{i}" for i in range(n)]


def scenario(tmp, prec_a, prec_b, out_a=100, out_b=100, eff_a="low", eff_b="low", n=20):
    """arm a and b each propose n private lemmas, the first int(prec*n) correct; some rows sit in the S4 sheet."""
    la, lb = lem("a", n), lem("b", n)
    truth = {l: int(i < round(prec_a * n)) for i, l in enumerate(la)}
    truth.update({l: int(i < round(prec_b * n)) for i, l in enumerate(lb)})
    p = make(tmp, {"llm_a": la, "llm_b": lb}, truth, in_s4=set(la[:3] + lb[:3]))
    raw = tmp / "raw"
    raw_log(raw, "a", out_a, eff_a)
    raw_log(raw, "b", out_b, eff_b)
    rows = S.load_arm_rows(**p)
    info = S.arm_info(["llm_a", "llm_b"], CFG, raw)
    return S.build_report(rows, info, CFG), rows


def test_scores_join_both_sheets(tmp_path):
    rep, rows = scenario(tmp_path, 0.8, 0.5)
    a = rep["arms"]["llm_a"]
    assert (a["proposed"], a["judged"], a["correct"]) == (20, 20, 16) and a["precision"] == pytest.approx(0.8)
    assert rep["arms"]["llm_b"]["precision"] == pytest.approx(0.5) and rep["judged_rows"] == 40
    assert a["model"] == "claude-sonnet-5-5" and a["effort"] == "low"


def test_clear_winner_even_if_costlier(tmp_path):
    rep, _ = scenario(tmp_path, 0.8, 0.5, out_a=250, out_b=50)
    assert rep["decision"]["winner"] == "llm_a" and rep["decision"]["rule"] == "higher_dev_precision"


def test_tie_prefers_cheaper(tmp_path):
    rep, _ = scenario(tmp_path, 0.75, 0.8, out_a=50, out_b=100)  # 5.0 points apart is a tie
    assert rep["decision"]["winner"] == "llm_a" and rep["decision"]["rule"] == "within_tie_lowest_cost_then_lower_effort"


def test_tie_same_cost_prefers_lower_effort(tmp_path):
    rep, _ = scenario(tmp_path, 0.8, 0.8, eff_a="medium", eff_b="low")
    assert rep["decision"]["winner"] == "llm_b"


def test_unresolved_tie(tmp_path):
    rep, _ = scenario(tmp_path, 0.8, 0.8)
    assert rep["decision"]["winner"] is None and rep["decision"]["rule"] == "unresolved_tie"


def test_over_cap_arm_is_ineligible(tmp_path):
    rep, _ = scenario(tmp_path, 0.9, 0.6, out_a=500, out_b=50)  # arm a projects to $5.78 > $4 cap
    assert rep["decision"]["over_cap"] == ["llm_a"] and rep["decision"]["winner"] == "llm_b"


def mutate(tmp, fn):
    la, lb = lem("a", 4), lem("b", 4)
    truth = {l: 1 for l in la + lb}
    p = make(tmp, {"llm_a": la, "llm_b": lb}, truth, in_s4={"a0", "b0"})
    fn(p)
    return p


def edit(path, fn, enc="utf-8-sig"):
    rows = list(csv.reader(open(path, encoding=enc, newline=""), delimiter="\t"))
    fn(rows)
    with open(path, "w", encoding=enc, newline="") as f:
        csv.writer(f, delimiter="\t", lineterminator="\r\n").writerows(rows)


@pytest.mark.parametrize("name,fn", [
    ("blank without UNSURE", lambda p: edit(p["b2_sheet"], lambda r: r[1].__setitem__(6, ""))),
    ("invalid correct", lambda p: edit(p["b2_sheet"], lambda r: r[1].__setitem__(6, "yes"))),
    ("b2 row missing from sheet", lambda p: edit(p["b2_sheet"], lambda r: r.pop())),
    ("sheet row not in key", lambda p: edit(p["b2_key"], lambda r: r.pop())),
    ("bad source name", lambda p: edit(p["b2_key"], lambda r: r[1].__setitem__(1, "mt_tilmash"))),
    ("s4 row missing", lambda p: edit(p["s4_sheet"], lambda r: r.pop(1))),
])
def test_bad_inputs_fail(tmp_path, name, fn):
    p = mutate(tmp_path, fn)
    with pytest.raises(M.ScoreError):
        S.load_arm_rows(**p)


def test_row_in_both_sheets_fails(tmp_path):
    p = mutate(tmp_path, lambda p: None)
    s4_first = list(csv.reader(open(p["s4_sheet"], encoding="utf-8-sig", newline=""), delimiter="\t"))[1]
    edit(p["b2_sheet"], lambda r: r.append(s4_first))
    with pytest.raises(M.ScoreError, match="both sheets"):
        S.load_arm_rows(**p)


def test_test_pool_synset_rejected(tmp_path):
    p = mutate(tmp_path, lambda p: None)
    with pytest.raises(M.ScoreError, match="test-pool"):
        S.load_arm_rows(test_ids={"s0"}, **p)