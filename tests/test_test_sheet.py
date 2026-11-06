import pytest

from kazwn import test_sheet as T
from kazwn.candidates import Candidate

TEST = {"t1-n", "t2-v"}
GL = {"t1-n": "g1", "t2-v": "g2"}


def C(sid, lk, src, pos="n"):
    return Candidate(sid, "x", lk, lk, pos, src, [], [])


@pytest.fixture
def data():
    by = {"dict": [C("t1-n", "а", "dict"), C("d-n", "я", "dict")],
          "mt": [C("t1-n", "а", "mt"), C("t1-n", "б", "mt")],
          "llm": [C("t1-n", "а", "llm"), C("t1-n", "в", "llm"), C("t2-v", "ту", "llm", "v")]}
    rows, keys = T.build(by, TEST, GL)
    sets = {"B0": {("t1-n", "а")}, "B1": {("t1-n", "а"), ("t1-n", "б")},
            "B2": {("t1-n", "а"), ("t1-n", "в"), ("t2-v", "ту")}, "B3": {("t1-n", "а")}}
    return rows, keys, sets


def test_systems_of():
    assert T.systems_of({"dict", "mt", "llm"}) == ["B0", "B1", "B2", "B3"]
    assert T.systems_of({"mt"}) == ["B1"]
    assert T.systems_of({"llm"}) == ["B2"]
    assert T.systems_of({"mt", "llm"}) == ["B1", "B2", "B3"]


def test_build_union_test_only(data):
    rows, keys, _ = data
    assert {r["key_id"] for r in rows} == {"t1-n|а", "t1-n|б", "t1-n|в", "t2-v|ту"}
    assert all(r["correct"] == "" for r in rows)
    assert "sources" not in rows[0] and "systems" not in rows[0]  # membership only in the key
    assert {k["key_id"]: k["systems"] for k in keys}["t1-n|а"] == "B0|B1|B2|B3"


def test_checker_rows_blank_same_set(data):
    rows, _, _ = data
    rows[0]["correct"], rows[0]["notes"] = "1", "x"
    c = T.checker_rows(rows)
    assert {r["key_id"] for r in c} == {r["key_id"] for r in rows}
    assert all(not (r["correct"] or r["error_category"] or r["notes"]) for r in c)


def test_verify_ok_and_failures(data):
    rows, keys, sets = data
    c = T.checker_rows(rows)
    assert T.verify(rows, keys, c, sets, TEST, GL) == []
    assert any("pair set differs" in x for x in T.verify(rows[1:], keys, None, sets, TEST, GL))
    bad = [dict(k) for k in keys]
    bad[0]["systems"] = "B1"
    assert any("key systems" in x for x in T.verify(rows, bad, None, sets, TEST, GL))
    leak = [dict(r) for r in c]
    leak[0]["correct"] = "1"
    assert any("labels or notes" in x for x in T.verify(rows, keys, leak, sets, TEST, GL))
    assert any("gloss differs" in x for x in T.verify(rows, keys, None, sets, TEST, {**GL, "t1-n": "zz"}))