import pytest

from kazwn import llm_final as F
from kazwn import llm_parse as P
from kazwn import llm_run as L
from kazwn import verify_llm_final as V
from kazwn.candidates import read_candidates, write_candidates, write_rejected
from test_llm import CFG, Fake, inputs

SCOPE = {"s1-n", "s2-v", "s3-s"}


def setup(tmp):
    fz = tmp / "freeze.json"
    L.freeze(CFG, "primary", freeze_path=fz)
    raw, cand = tmp / "raw", tmp / "cand"
    plan = [("dev_t", {"dev"}, '{"lemmas": ["мысық"]}'), ("rest_t", {"rest"}, '{"lemmas": ["жүгіру", "бару"]}'),
            ("test_t", {"test"}, '{"lemmas": ["үлкен"]}')]
    for tag, pools, reply in plan:
        L.run(inputs(), pools, tag, "primary", CFG, allow_test=True, client=Fake([reply]), raw_dir=raw, freeze_path=fz, log=lambda *_: None)
        cands, rejs, _ = P.parse_rows(L.read_raw(raw / f"{tag}.jsonl"))
        write_candidates("llm", cands, cand / f"llm_{tag}.tsv")
        write_rejected("llm", rejs, cand / f"llm_{tag}_rejected.tsv")
    return fz, raw, cand


TAGS = ["dev_t", "rest_t", "test_t"]


def test_convert_and_verify_ok(tmp_path):
    fz, raw, cand = setup(tmp_path)
    assert F.check_runs(TAGS, SCOPE, fz, raw) == []
    assert F.convert(TAGS, cand) == (4, 0, 3)
    assert V.check(TAGS, CFG, SCOPE, fz, raw, cand) == []
    assert all(c.source == "llm" for c in read_candidates(cand / "llm.tsv"))


def test_detects_missing_synset_and_overlap(tmp_path):
    fz, raw, cand = setup(tmp_path)
    assert any("cover 2 of 3" in p for p in F.check_runs(["dev_t", "rest_t"], SCOPE, fz, raw))
    assert any("more than one tag" in p for p in F.check_runs(TAGS + ["dev_t"], SCOPE, fz, raw))


def test_detects_tampered_llm_tsv(tmp_path):
    fz, raw, cand = setup(tmp_path)
    F.convert(TAGS, cand)
    rows = read_candidates(cand / "llm.tsv")
    rows[0].lemma_kk = "өзге"
    write_candidates("llm", rows, cand / "llm.tsv")
    assert any("differs" in f for f in V.check(TAGS, CFG, SCOPE, fz, raw, cand))


def test_detects_run_with_other_effort(tmp_path):
    fz, raw, cand = setup(tmp_path)
    L.run(inputs(), {"dev"}, "dev_m", "primary", dict(CFG, effort="medium"), client=Fake(['{"lemmas": []}']), raw_dir=raw, log=lambda *_: None)
    assert any("frozen" in p for p in F.check_runs(["dev_m", "rest_t", "test_t"], SCOPE, fz, raw))


def test_sources_block():
    b = F.sources_block(["a", "b"], {"model": "m", "effort": "high", "max_tokens": 3000, "prompt_file": "p.txt", "prompt_sha256": "ab" * 32}, 1.5)
    assert "effort high" in b and "$1.5000" in b and "a, b" in b


def test_missing_parsed_files_reported_not_crashed(tmp_path):
    fz, raw, cand = setup(tmp_path)
    assert F.missing_files(TAGS, cand) == []
    (cand / "llm_rest_t.tsv").unlink()
    assert F.missing_files(TAGS, cand) == ["llm_rest_t.tsv"]
    fails = V.check(TAGS, CFG, SCOPE, fz, raw, cand)
    assert any("missing file: llm_rest_t.tsv" in f for f in fails)