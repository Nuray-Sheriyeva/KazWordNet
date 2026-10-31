import csv
import pytest

from kazwn import mt_dev_score as m

SEL = {"finalists": ["tilmash", "nllb600m"],
       "engines": {"tilmash": {"incremental_coverage": 0.96}, "nllb600m": {"incremental_coverage": 1.0}}}


def write(tmp, spec, crlf=True, extra=None):
    """spec: {(sources...): [(correct, cat, pos), ...]} -> sheet + key files."""
    sheet, key, i = [], [], 0
    for srcs, items in spec.items():
        for c, cat, pos in items:
            i += 1
            syn = f"s{i // 2}-{pos}"
            lemma = f"сөз{i}"
            kid = f"{syn}|{lemma}"
            note = "UNSURE: x" if c == "" else ""
            sheet.append([kid, syn, pos, "en", "gloss", lemma, c, cat, note])
            key.append([kid, "|".join(srcs), ""])
    if extra:
        extra(sheet, key)
    nl = "\r\n" if crlf else "\n"
    sp, kp = tmp / "sheet.tsv", tmp / "key.tsv"
    with open(sp, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, delimiter="\t", lineterminator=nl).writerows([m.SHEET_COLS] + sheet)
    with open(kp, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, delimiter="\t", lineterminator=nl).writerows([m.KEY_COLS] + key)
    return sp, kp


def ok(n):
    return [("1", "", "n")] * n


def bad(n, cat="wrong_sense", pos="n"):
    return [("0", cat, pos)] * n


def test_scores_and_per_pos(tmp_path):
    spec = {("b0_dict", "mt_tilmash"): ok(3) + bad(1, "calque", "v"),
            ("mt_tilmash",): ok(1) + [("", "", "a")] + bad(1, "form", "s"),
            ("mt_nllb600m",): ok(2) + bad(2)}
    rows = m.load(*write(tmp_path, spec))
    t = m.score_source(rows, "mt_tilmash")
    assert (t["proposed"], t["judged"], t["correct"]) == (7, 6, 4)
    assert t["excluded_blank"] == 1 and t["excluded_unsure"] == 1
    assert t["precision"] == pytest.approx(4 / 6)
    assert t["wilson_lo"] < t["precision"] < t["wilson_hi"]
    assert t["per_pos"]["v"]["judged"] == 1 and t["per_pos"]["a"]["judged"] == 1  # s counted as a
    assert t["error_categories"] == {"calque": 1, "form": 1}
    assert t["only_this_source"]["judged"] == 2
    b = m.score_source(rows, "b0_dict")
    assert b["judged"] == 4 and b["correct"] == 3


def sel_spec(pt, nt, pn, nn):
    return {("mt_tilmash",): ok(pt) + bad(nt - pt), ("mt_nllb600m",): ok(pn) + bad(nn - pn), ("b0_dict",): ok(1)}


@pytest.mark.parametrize("spec,winner,rule", [
    (sel_spec(8, 10, 7, 10), "tilmash", "higher_dev_precision"),
    (sel_spec(7, 10, 8, 10), "nllb600m", "higher_dev_precision"),
    (sel_spec(15, 20, 16, 20), "tilmash", "within_tie_permissive_license"),  # gap exactly 5.0 is a tie
    (sel_spec(8, 10, 8, 10), "tilmash", "within_tie_permissive_license"),
])
def test_decision(tmp_path, spec, winner, rule):
    rep = m.build_report(m.load(*write(tmp_path, spec)), SEL)
    assert rep["decision"]["winner"] == winner and rep["decision"]["rule"] == rule


def test_tie_without_permissive_uses_coverage(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PERMISSIVE", set())
    d = m.build_report(m.load(*write(tmp_path, sel_spec(8, 10, 8, 10))), SEL)["decision"]
    assert d["winner"] == "nllb600m" and d["rule"] == "within_tie_incremental_coverage"


def test_unresolved_tie(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "PERMISSIVE", set())
    sel = {"finalists": SEL["finalists"], "engines": {e: {"incremental_coverage": 1.0} for e in SEL["finalists"]}}
    d = m.build_report(m.load(*write(tmp_path, sel_spec(8, 10, 8, 10))), sel)["decision"]
    assert d["winner"] is None and d["rule"] == "unresolved_tie"


def test_bom_and_lf_also_accepted(tmp_path):
    sp, kp = write(tmp_path, sel_spec(1, 2, 1, 2), crlf=False)
    sp.write_bytes(b"\xef\xbb\xbf" + sp.read_bytes())
    assert len(m.load(sp, kp)) == 5


@pytest.mark.parametrize("mutate", [
    lambda s, k: s[0].__setitem__(6, "yes"),
    lambda s, k: s[0].__setitem__(7, "calque"),            # correct=1 with category
    lambda s, k: (s[0].__setitem__(6, "0"), s[0].__setitem__(7, "")),  # incorrect without category
    lambda s, k: (s[0].__setitem__(6, "0"), s[0].__setitem__(7, "bogus")),
    lambda s, k: (s[0].__setitem__(6, ""), s[0].__setitem__(8, "")),   # blank without UNSURE
    lambda s, k: k.pop(),                                   # key row missing
    lambda s, k: k[0].__setitem__(1, "b0_dict|nope"),
])
def test_bad_sheet_fails(tmp_path, mutate):
    sp, kp = write(tmp_path, sel_spec(2, 3, 2, 3), extra=mutate)
    with pytest.raises(m.ScoreError):
        m.load(sp, kp)


def test_test_pool_rows_rejected(tmp_path):
    sp, kp = write(tmp_path, sel_spec(1, 2, 1, 2))
    syn = next(csv.DictReader(open(sp, encoding="utf-8"), delimiter="\t"))["synset_id"]
    with pytest.raises(m.ScoreError, match="test-pool"):
        m.load(sp, kp, test_ids={syn})


def test_wrong_delimiter_fails(tmp_path):
    sp, kp = write(tmp_path, sel_spec(1, 2, 1, 2))
    sp.write_text(sp.read_text(encoding="utf-8").replace("\t", ","), encoding="utf-8")
    with pytest.raises(m.ScoreError, match="header"):
        m.load(sp, kp)