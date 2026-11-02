from kazwn import judge_sheet_b2 as B
from kazwn.candidates import Candidate


def cand(sid, lemma, pos="n"):
    return Candidate(sid, "en", lemma, lemma, pos, "llm", [{"e": 1}], [])


def test_new_rows_exclude_s4_and_key_records_all():
    sources = {"llm_a": [cand("s1", "күн"), cand("s1", "түн"), cand("s2", "ай")],
               "llm_b": [cand("s1", "күн"), cand("s2", "жыл"), cand("s9", "тау")]}
    rows, keys = B.build(sources, {"s1", "s2"}, {"s1": "g1", "s2": "g2"}, {"s1|түн"})
    assert {r["key_id"] for r in rows} == {"s1|күн", "s2|ай", "s2|жыл"}
    kd = {k["key_id"]: k for k in keys}
    assert set(kd) == {"s1|күн", "s1|түн", "s2|ай", "s2|жыл"}  # s9 is not a dev synset
    assert kd["s1|күн"]["sources"] == "llm_a|llm_b" and kd["s1|түн"]["in_s4_sheet"] == "1"
    assert kd["s2|жыл"]["in_s4_sheet"] == "0" and kd["s2|жыл"]["sources"] == "llm_b"
    assert all(set(r) == set(B.J.COLS) and r["correct"] == "" for r in rows)  # blind: no source columns


def test_order_is_deterministic():
    sources = {"llm_a": [cand("s1", w) for w in ["а", "б", "в", "г", "д"]]}
    r1, _ = B.build(sources, {"s1"}, {"s1": "g"}, set())
    r2, _ = B.build(sources, {"s1"}, {"s1": "g"}, set())
    assert [r["lemma_kk"] for r in r1] == [r["lemma_kk"] for r in r2]