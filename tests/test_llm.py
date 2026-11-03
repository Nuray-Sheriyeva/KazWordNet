import json
from types import SimpleNamespace

import pytest

from kazwn import llm_parse as P
from kazwn import llm_run as L
from kazwn import verify_llm as V
from kazwn.candidates import read_candidates, read_rejected, write_candidates, write_rejected

CFG = L.load_cfg()
PROMPT = L.ROOT / CFG["prompt_file"]


def scope_rows():
    return [
        {"synset_id": "s1-n", "pos": "n", "lemmas_en": "cat|true_cat", "gloss": "a feline", "examples": "a cat sat || cats purr", "hypernym_lemmas": "feline"},
        {"synset_id": "s2-v", "pos": "v", "lemmas_en": "run", "gloss": "move fast", "examples": "", "hypernym_lemmas": ""},
        {"synset_id": "s3-s", "pos": "s", "lemmas_en": "big", "gloss": "large", "examples": "", "hypernym_lemmas": ""},
    ]


def inputs():
    return L.build_inputs(scope_rows(), {"s1-n"}, {"s3-s"})


class Fake:
    def __init__(self, replies, out_tokens=100, stop="end_turn"):
        self.replies, self.out, self.stop, self.calls = list(replies), out_tokens, stop, []
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kw):
        self.calls.append(kw)
        text = self.replies.pop(0)
        return SimpleNamespace(content=[SimpleNamespace(type="thinking", text="x"), SimpleNamespace(type="text", text=text)],
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=self.out), stop_reason=self.stop)


def test_pools_and_split():
    i = {x["synset_id"]: x for x in inputs()}
    assert [x["pool"] for x in i.values()] == ["dev", "rest", "test"]
    assert i["s1-n"]["lemmas_en"] == ["cat", "true cat"] and i["s1-n"]["examples"] == ["a cat sat", "cats purr"]


def test_render_and_adjective_name():
    system, user_t = L.load_prompt(PROMPT)
    s, u = L.render(system, user_t, inputs()[2], CFG)
    assert "adjective" in u and "Examples: none" in u and "<<" not in s + u and "at most 6" in s


def test_run_logs_and_request_shape(tmp_path):
    fake = Fake(['{"lemmas": ["мысық"]}', '{"lemmas": []}'])
    n, spent = L.run(inputs(), {"dev", "rest"}, "t", "primary", CFG, client=fake, raw_dir=tmp_path, log=lambda *_: None)
    assert n == 2 and spent == pytest.approx(2 * (1000 * 2 + 100 * 10) / 1e6)
    kw = fake.calls[0]
    assert kw["model"] == "claude-sonnet-5-5" and "temperature" not in kw
    assert kw["output_config"]["effort"] == CFG["effort"] and kw["output_config"]["format"]["type"] == "json_schema"
    rows = L.read_raw(tmp_path / "t.jsonl")
    assert rows[0]["system"] and rows[0]["user"] and rows[0]["usage"]["output_tokens"] == 100


def test_resume_and_mixing_guard(tmp_path):
    L.run(inputs(), {"dev"}, "t", "primary", CFG, client=Fake(['{"lemmas": []}']), raw_dir=tmp_path, log=lambda *_: None)
    fake = Fake([])
    n, _ = L.run(inputs(), {"dev"}, "t", "primary", CFG, client=fake, raw_dir=tmp_path, log=lambda *_: None)
    assert n == 0 and not fake.calls
    with pytest.raises(L.LLMError, match="another model"):
        L.run(inputs(), {"dev"}, "t", "fallback", CFG, client=Fake([]), raw_dir=tmp_path, log=lambda *_: None)


def test_cap_stops_run(tmp_path):
    cfg = dict(CFG, cap_usd=0.005)
    fake = Fake(['{"lemmas": []}'] * 3, out_tokens=100)  # $0.003 per call
    n, spent = L.run(inputs(), {"dev", "rest"}, "t", "primary", cfg, client=fake, raw_dir=tmp_path, log=lambda *_: None)
    assert n == 2 and spent >= 0.005  # stops once the cap is reached, before a third call


def test_test_pool_guard_and_freeze(tmp_path):
    kw = dict(client=Fake(['{"lemmas": []}']), raw_dir=tmp_path, log=lambda *_: None)
    with pytest.raises(L.LLMError, match="--allow-test"):
        L.run(inputs(), {"test"}, "t", "primary", CFG, **kw)
    fp = tmp_path / "freeze.json"
    with pytest.raises(L.LLMError, match="--freeze"):
        L.run(inputs(), {"test"}, "t", "primary", CFG, allow_test=True, freeze_path=fp, **kw)
    L.freeze(CFG, "primary", freeze_path=fp)
    with pytest.raises(L.LLMError, match="already exists"):
        L.freeze(CFG, "primary", freeze_path=fp)
    n, _ = L.run(inputs(), {"test"}, "t", "primary", CFG, allow_test=True, freeze_path=fp, **kw)
    assert n == 1
    with pytest.raises(L.LLMError, match="mismatch"):
        L.run(inputs(), {"test"}, "u", "fallback", CFG, allow_test=True, freeze_path=fp, **kw)


def test_projection_rule(tmp_path):
    L.run(inputs(), {"dev", "rest"}, "pilot", "primary", CFG, client=Fake(['{"lemmas": []}'] * 2, out_tokens=100), raw_dir=tmp_path, log=lambda *_: None)
    rep = L.project("pilot", CFG, tmp_path)  # $0.003 per prompt -> 0.003 * (400 + 425) = 2.475
    assert rep["projected_total_usd"] == pytest.approx(0.003 * 825) and rep["decision"] == "claude-sonnet-5-5"
    L.run(inputs(), {"dev", "rest"}, "pilot2", "primary", CFG, client=Fake(['{"lemmas": []}'] * 2, out_tokens=500), raw_dir=tmp_path, log=lambda *_: None)
    assert L.project("pilot2", CFG, tmp_path)["decision"] == "claude-haiku-5-5"  # $0.007 -> 5.78 > cap


def test_parse_and_verify(tmp_path):
    replies = ['{"lemmas": ["мысық", "Mysyk", "мысық"]}', '{"lemmas": ["жүгіру", "бару"]}']
    L.run(inputs(), {"dev", "rest"}, "t", "primary", CFG, client=Fake(replies), raw_dir=tmp_path, log=lambda *_: None)
    rows = L.read_raw(tmp_path / "t.jsonl")
    cands, rejs, stats = P.parse_rows(rows)
    assert {c.lemma_kk for c in cands} == {"мысық", "жүгіру", "бару"} and all(c.source == "llm" for c in cands)
    assert [r.reason for r in rejs] == ["latin_script"]
    assert next(c for c in cands if c.lemma_kk == "бару").flags == []  # ends in -у, no verb_form_check
    write_candidates("llm", cands, tmp_path / "llm_t.tsv")
    write_rejected("llm", rejs, tmp_path / "llm_t_rejected.tsv")
    fails, _ = V.check("t", CFG, raw_dir=tmp_path, cand_dir=tmp_path, scope_ids={"s1-n", "s2-v", "s3-s"})
    assert fails == []
    rows[0]["cost_usd"] += 1
    (tmp_path / "t.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    fails, _ = V.check("t", CFG, raw_dir=tmp_path, cand_dir=tmp_path)
    assert any("cost" in f for f in fails)


def test_parse_bad_responses():
    base = {"synset_id": "s1", "lemma_en": "a", "pos": "n", "model": "m", "prompt_sha256": "0" * 64, "input_id": "s1"}
    rows = [dict(base, response_text="not json", stop_reason="end_turn"),
            dict(base, response_text='{"lemmas": []}', stop_reason="max_tokens"),
            dict(base, response_text='{"lemmas": []}', stop_reason="end_turn")]
    cands, rejs, stats = P.parse_rows(rows)
    assert not cands and [r.reason for r in rejs] == ["parse_fail:json", "stop:max_tokens"] and stats["empty_list"] == 1

def test_effort_override_and_mixing_guard(tmp_path):
    cfg_m = dict(CFG, effort="medium")
    fake = Fake(['{"lemmas": []}'])
    L.run(inputs(), {"dev"}, "m", "primary", cfg_m, client=fake, raw_dir=tmp_path, log=lambda *_: None)
    assert fake.calls[0]["output_config"]["effort"] == "medium"
    assert L.read_raw(tmp_path / "m.jsonl")[0]["effort"] == "medium"
    with pytest.raises(L.LLMError, match="model/prompt/effort"):
        L.run(inputs(), {"dev"}, "m", "primary", CFG, client=Fake([]), raw_dir=tmp_path, log=lambda *_: None)


def test_freeze_blocks_effort_change(tmp_path):
    fp = tmp_path / "freeze.json"
    L.freeze(CFG, "primary", freeze_path=fp)
    with pytest.raises(L.LLMError, match="effort"):
        L.run(inputs(), {"test"}, "t", "primary", dict(CFG, effort="medium"), allow_test=True, freeze_path=fp,
              client=Fake([]), raw_dir=tmp_path, log=lambda *_: None)


def test_model_id_override_and_projection_for_other_models(tmp_path):
    cfg = dict(CFG, prices_usd_per_mtok=dict(CFG["prices_usd_per_mtok"], **{"claude-opus-5-5": {"in": 4.0, "out": 20.0}}))
    fake = Fake(['{"lemmas": []}'])
    L.run(inputs(), {"dev"}, "o", "claude-opus-5-5", cfg, client=fake, raw_dir=tmp_path, log=lambda *_: None)
    assert fake.calls[0]["model"] == "claude-opus-5-5"
    rep = L.project("o", cfg, tmp_path)  # $0.006 per prompt -> 0.006 * 825 = 4.95 > cap
    assert rep["model"] == "claude-opus-5-5" and rep["effort"] == CFG["effort"] and rep["decision"] == "over_cap"
    with pytest.raises(L.LLMError, match="no price"):
        L.run(inputs(), {"dev"}, "x", "claude-unknown", CFG, client=Fake([]), raw_dir=tmp_path, log=lambda *_: None)
    fz = tmp_path / "fz.json"
    assert L.freeze(cfg, "claude-opus-5-5", freeze_path=fz)["model"] == "claude-opus-5-5"