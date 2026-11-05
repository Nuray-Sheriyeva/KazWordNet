import pytest

from kazwn import b3_dev_score as D
from kazwn import systems as S
from kazwn import verify_b3 as V
from kazwn.candidates import Candidate
from kazwn.mt_dev_score import ScoreError

DEV, TEST = {"d1-n", "d2-v"}, {"t1-n"}


def C(sid, lk, src, pos="n", en="x", flags=(), ev=None):
    return Candidate(sid, en, lk, lk, pos, src, ev if ev is not None else [{"src": src, "k": lk}], list(flags))


@pytest.fixture
def srcs():
    return {
        "dict": [C("d1-n", "а", "dict"), C("d1-n", "б", "dict"), C("d2-v", "ту", "dict", "v", en="e1"),
                 C("t1-n", "а", "dict"), C("r1-n", "в", "dict")],
        "mt": [C("d1-n", "а", "mt", en="y"), C("d1-n", "г", "mt"), C("t1-n", "а", "mt"), C("r1-n", "в", "mt")],
        "llm": [C("d1-n", "а", "llm"), C("d1-n", "б", "llm", flags=["multiword"]), C("d1-n", "д", "llm"),
                C("d2-v", "ту", "llm", "v", en="e2"), C("t1-n", "ж", "llm")],
    }


def keyset(rows):
    return {(r["synset_id"], r["lemma_kk"]) for r in rows}


def test_vote_and_union(srcs):
    b1, b3 = S.build(srcs)
    assert keyset(b1) == {("d1-n", "а"), ("d1-n", "б"), ("d1-n", "г"), ("d2-v", "ту"), ("t1-n", "а"), ("r1-n", "в")}
    assert keyset(b3) == {("d1-n", "а"), ("d1-n", "б"), ("d2-v", "ту"), ("t1-n", "а"), ("r1-n", "в")}
    assert ("d1-n", "д") not in keyset(b1)  # llm only: never in B1, never in B3
    assert keyset(b3) <= keyset(b1)


def test_row_fields(srcs):
    _, b3 = S.build(srcs)
    r = next(r for r in b3 if r["lemma_kk"] == "а" and r["synset_id"] == "d1-n")
    assert r["sources"] == "dict|llm|mt" and r["votes"] == "3" and r["lemma_en"] == "x|y"
    assert len(json_ev(r)) == 3
    r = next(r for r in b3 if r["lemma_kk"] == "ту")
    assert r["sources"] == "dict|llm" and r["lemma_en"] == "e1|e2"
    r = next(r for r in b3 if r["lemma_kk"] == "б")
    assert r["flags"] == "multiword"  # D9: flags carried, not filtered


def json_ev(r):
    import json
    return json.loads(r["evidence"])


def test_keep_excludes_test(srcs):
    b1, b3 = S.build(srcs, lambda sid: sid not in TEST)
    assert all(r["synset_id"] != "t1-n" for r in b1 + b3)


def test_pos_mismatch_and_wrong_sources(srcs):
    srcs["mt"].append(C("d1-n", "б", "mt", "v"))
    with pytest.raises(S.BuildError, match="POS mismatch"):
        S.build(srcs)
    with pytest.raises(S.BuildError, match="need exactly"):
        S.build({"dict": []})
    bad = {"dict": [C("d1-n", "а", "mt")], "mt": [], "llm": []}
    with pytest.raises(S.BuildError, match="row source 'mt' in the 'dict' file"):
        S.build(bad)


def test_roundtrip_and_header(tmp_path, srcs):
    b1, _ = S.build(srcs)
    p = tmp_path / "b1.tsv"
    S.write_rows(p, b1)
    assert S.read_rows(p) == b1
    p.write_text("a\tb\n", encoding="utf-8")
    with pytest.raises(S.BuildError, match="header"):
        S.read_rows(p)


def test_counts_hide_test(srcs):
    b1, b3 = S.build(srcs)
    sets = {"b3": keyset(b3)}
    rep = S.counts(sets, b3, DEV, TEST, DEV | TEST | {"r1-n"})
    assert set(rep["systems"]["b3"]) == {"dev", "rest"}
    assert rep["pool_sizes"] == {"dev": 2, "rest": 1}
    assert "t1-n" not in str(rep["b3_vote_combinations"]) and rep["test"].startswith("withheld")


def test_verify_passes_and_catches(srcs):
    b1, b3 = S.build(srcs)
    assert V.verify(srcs, b1, b3, DEV, TEST, True) == []
    f = V.verify(srcs, b1, b3, DEV, TEST, False)
    assert any("test-pool row" in x for x in f)
    b1n, b3n = S.build(srcs, lambda sid: sid not in TEST)
    assert V.verify(srcs, b1n, b3n, DEV, TEST, False) == []
    bad = [dict(r) for r in b3n]
    bad[0]["votes"] = "1"
    assert any("bad votes" in x for x in V.verify(srcs, b1n, bad, DEV, TEST, False))
    assert any("pair set differs" in x for x in V.verify(srcs, b1n, b3n[1:], DEV, TEST, False))
    ev = [dict(r, evidence="[]") for r in b3n]
    assert any("evidence of" in x for x in V.verify(srcs, b1n, ev, DEV, TEST, False))


def J(sid, lk, c, cat="", grp="n"):
    return {"key_id": f"{sid}|{lk}", "synset_id": sid, "grp": grp, "c": c, "cat": cat, "unsure": False}


def test_verify_missing_judgment(srcs):
    b1, b3 = S.build(srcs, lambda sid: sid not in TEST)
    full = {f"{r['synset_id']}|{r['lemma_kk']}": 1 for r in b1}
    full.update({"d1-n|д": 1})
    assert V.verify(srcs, b1, b3, DEV, TEST, False, full) == []
    del full["d1-n|г"]
    assert any("without judgment" in x for x in V.verify(srcs, b1, b3, DEV, TEST, False, full))


def test_score_and_gate_preview(srcs):
    _, b3 = S.build(srcs, lambda sid: sid not in TEST)
    judg = {"d1-n|а": J("d1-n", "а", 1), "d1-n|б": J("d1-n", "б", 0, "wrong_sense"),
            "d2-v|ту": J("d2-v", "ту", None, grp="v")}
    pairs = D.dev_pairs(b3, DEV)
    s = D.score(pairs, judg, 2)
    assert (s["proposed"], s["judged"], s["correct"], s["excluded_blank"]) == (3, 2, 1, 1)
    assert s["precision"] == 0.5 and s["error_categories"] == {"wrong_sense": 1}
    assert s["by_flag"]["multiword"]["judged"] == 1 and s["by_flag"]["no_flag"]["correct"] == 1
    assert s["coverage_proposed"]["value"] == 1.0 and s["coverage_judged_correct"]["value"] == 0.5
    g = D.gate_preview(s, 2)
    assert g["passed"] is False and "precision" in g["report"]
    with pytest.raises(ScoreError, match="without a judgment"):
        D.score(pairs, {"d1-n|а": J("d1-n", "а", 1)}, 2)


def test_merge_judgments_conflict():
    a, b = [J("s", "x", 1)], [J("s", "x", 1), J("s", "y", 0, "form")]
    assert set(D.merge_judgments(a, b)) == {"s|x", "s|y"}
    with pytest.raises(ScoreError, match="differ"):
        D.merge_judgments(a, [J("s", "x", 0, "form")])