import json

from kazwn.candidates import normalize
from kazwn.mt_inputs import build_inputs
from kazwn.mt_parse import extract_head, parse_rows
from kazwn.mt_run import run_engine

ROWS = [
    {"synset_id": "1-n", "pos": "n", "lemmas_en": "bank|depository_financial_institution", "gloss": "a financial institution"},
    {"synset_id": "2-v", "pos": "v", "lemmas_en": "write", "gloss": "to form letters"},
    {"synset_id": "3-n", "pos": "n", "lemmas_en": "cat", "gloss": "a feline"},
]


def test_inputs_pools_and_text():
    ins = build_inputs(ROWS, {"2-v"}, {"3-n"})
    assert [i["input_id"] for i in ins] == ["1-n|bank", "1-n|depository financial institution", "2-v|write", "3-n|cat"]
    assert [i["pool"] for i in ins] == ["rest", "rest", "dev", "test"]
    assert ins[1]["text"] == "depository financial institution: a financial institution"


def test_extract_head():
    assert extract_head("банк: қаржы мекемесі") == ("банк", "")
    assert extract_head("банк\uff1a қаржы") == ("банк", "")
    assert extract_head("оқып шығу: ...")[0] == "оқып шығу"
    assert extract_head("Қаржы мекемесі")[1] == "parse_fail:no_colon"
    assert extract_head(": қаржы")[1] == "parse_fail:empty_head"
    assert extract_head("бұл өте ұзақ сөйлем болып кетті: ...")[1] == "parse_fail:head_too_long"


class Fake:
    calls = 0
    OUT = {"bank: a financial institution": "банк: қаржы мекемесі",
           "write: to form letters": "жаз: әріптер жазу",
           "cat: a feline": "Мысық"}

    def translate(self, texts):
        Fake.calls += 1
        return [self.OUT.get(t, "") for t in texts]


def test_run_resume_and_parse(tmp_path):
    rows = [dict(r, **{"text": f"{r['lemma_en']}: {r['text_gloss']}"}) for r in [
        {"input_id": "1-n|bank", "synset_id": "1-n", "lemma_en": "bank", "pos": "n", "pool": "rest", "text_gloss": "a financial institution"},
        {"input_id": "2-v|write", "synset_id": "2-v", "lemma_en": "write", "pos": "v", "pool": "dev", "text_gloss": "to form letters"},
        {"input_id": "3-n|cat", "synset_id": "3-n", "lemma_en": "cat", "pos": "n", "pool": "rest", "text_gloss": "a feline"}]]
    out = tmp_path / "fake.jsonl"
    assert run_engine(Fake(), rows[:2], out, 8) == 2
    assert run_engine(Fake(), rows, out, 8) == 1          # resume: only the missing input
    assert run_engine(Fake(), rows, out, 8) == 0
    raw = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert len(raw) == 3
    cands, rejs, fail = parse_rows(raw, "fake")
    assert {c.lemma_kk for c in cands} == {"банк", "жаз"}
    assert "verb_form_check" in [c for c in cands if c.lemma_kk == "жаз"][0].flags   # stem, flagged not fixed
    assert dict(fail) == {"parse_fail:no_colon": 1}                                   # 'Мысық' has no colon
    assert [r.reason for r in rejs] == ["parse_fail:no_colon"]
    assert cands[0].evidence[0]["engine"] == "fake" and normalize("банк", "n").ok