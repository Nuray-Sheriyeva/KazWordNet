import csv
import json

import pytest

from kazwn import candidates as C
from kazwn import mt_final as F
from kazwn import verify_mt_final as V


def setup(tmp_path, pools="dev,rest,test", drop_raw=0):
    cd, rd = tmp_path / "cand", tmp_path / "raw"
    rd.mkdir()
    ev = {"engine": "tilmash", "input_id": "x", "raw": "r"}
    words = ["күн", "түн", "ай", "жыл"]
    cands = [C.Candidate(f"s{i}", "en", w, w.capitalize(), "n", "mt", [dict(ev, input_id=f"s{i}|en")], []) for i, w in enumerate(words)]
    rejs = [C.Rejected("s9", "en", "bad", "n", "mt", "x", [ev])]
    C.write_candidates("mt", cands, cd / "mt_tilmash.tsv")
    C.write_rejected("mt", rejs, cd / "mt_tilmash_rejected.tsv")
    ids = [f"s{i}|en" for i in range(5)]
    with open(rd / "inputs.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t"); w.writerow(["input_id", "synset_id"]); [w.writerow([i, i.split("|")[0]]) for i in ids]
    (rd / "tilmash.jsonl").write_text("\n".join(json.dumps({"input_id": i}) for i in ids[: 5 - drop_raw]), encoding="utf-8")
    (rd / "tilmash.meta.json").write_text(json.dumps({"pools": pools, "revision": "abc"}), encoding="utf-8")
    with open(tmp_path / "scope.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t"); w.writerow(["synset_id"]); [w.writerow([f"s{i}"]) for i in range(10)]
    return cd, rd


def run(tmp_path, cd, rd):
    return V.check("tilmash", cd, rd, rd / "inputs.tsv", tmp_path / "scope.tsv")


def test_convert_and_verify_ok(tmp_path):
    cd, rd = setup(tmp_path)
    assert F.convert("tilmash", cd) == (4, 1, 4)
    assert run(tmp_path, cd, rd) == []
    assert all(c.source == "mt" for c in C.read_candidates(cd / "mt.tsv"))


def test_detects_tampered_mt(tmp_path):
    cd, rd = setup(tmp_path)
    F.convert("tilmash", cd)
    rows = C.read_candidates(cd / "mt.tsv")
    rows[0].lemma_kk = "өзге"
    C.write_candidates("mt", rows, cd / "mt.tsv")
    assert any("differs" in f for f in run(tmp_path, cd, rd))


def test_detects_test_pool_not_run(tmp_path):
    cd, rd = setup(tmp_path, drop_raw=1)
    F.convert("tilmash", cd)
    assert any("no raw output" in f for f in run(tmp_path, cd, rd))


def test_detects_meta_without_test(tmp_path):
    cd, rd = setup(tmp_path, pools="dev,rest")
    F.convert("tilmash", cd)
    assert any("pools" in f for f in run(tmp_path, cd, rd))


def test_chosen_refuses_unresolved(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"decision": {"winner": None}}))
    with pytest.raises(SystemExit):
        F.chosen(p)
    p.write_text(json.dumps({"decision": {"winner": "tilmash"}}))
    assert F.chosen(p)[0] == "tilmash"


def test_sources_block():
    rep = {"decision": {"rule": "higher_dev_precision", "finalists": ["tilmash", "nllb600m"], "dev_precision": {"tilmash": 0.6867, "nllb600m": 0.5699}}}
    b = F.sources_block("tilmash", rep, {"revision": "abc"})
    assert "issai/tilmash" in b and "0.687" in b and '"revision": "abc"' in b