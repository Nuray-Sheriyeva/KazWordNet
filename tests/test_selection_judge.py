from kazwn.candidates import Candidate
from kazwn.judge_sheet import build_rows, check_rows, merge_sheet
from kazwn.mt_selection import proxies, rank


def C(sid, lk, src, input_id=None):
    ev = [{"engine": src, "input_id": input_id or f"{sid}|x", "raw": ""}]
    return Candidate(sid, "x", lk, lk, "n", src, ev, [])


RAW = [{"input_id": "1|x", "synset_id": "1", "output": "банк: ..."},
       {"input_id": "2|x", "synset_id": "2", "output": "no colon here"},
       {"input_id": "3|x", "synset_id": "3", "output": "кітап: ..."},
       {"input_id": "4|x", "synset_id": "4", "output": "ит: ..."}]


def test_proxies_and_rank():
    pool = {"1", "2", "3", "4"}
    b0 = [C("1", "банк", "dict"), C("3", "кітап", "dict")]            # covers 1 and 3
    mt = [C("1", "банк", "mt"), C("3", "оқулық", "mt"), C("4", "ит", "mt")]
    m = proxies(RAW, mt, b0, pool)
    assert m["parse_success"] == 0.75 and m["s1_survival"] == 1.0 and m["eligible"]
    assert m["b0_hit_rate"] == 0.5                  # synset 1 hits, 3 does not
    assert m["incremental_coverage"] == 0.5         # of uncovered {2,4}, only 4 has an MT candidate
    assert m["candidate_overlap_with_b0"] == 0.5    # 1 of 2 MT candidates on B0-covered synsets
    bad = dict(m, eligible=False)
    assert rank({"a": bad, "b": m, "c": dict(m, b0_hit_rate=0.9)}) == ["c", "b"]


def test_build_merge_check():
    srcs = {"b0_dict": [C("1", "банк", "dict"), C("9", "ит", "dict")], "mt_a": [C("1", "банк", "mt"), C("1", "қор", "mt")]}
    rows, keys = build_rows(srcs, {"1"}, {"1": "a bank"})
    assert [r["lemma_kk"] for r in rows if r["synset_id"] == "1"].count("банк") == 1   # judged once
    assert {r["synset_id"] for r in rows} == {"1"}                                      # non-dev excluded
    assert [k for k in keys if k["key_id"] == "1|банк"][0]["sources"] == "b0_dict|mt_a"
    assert all("sources" not in r for r in rows)                                        # blind sheet
    rows[0]["correct"] = "1"
    new, _ = build_rows({"mt_b": [C("1", "жаңа", "mt")]}, {"1"}, {"1": "a bank"})
    merged = merge_sheet(rows, new)
    assert merged[0]["correct"] == "1" and len(merged) == len(rows) + 1                 # judgments preserved
    merged[1]["correct"] = "x"
    assert check_rows(merged)["invalid_rows"] == [merged[1]["key_id"]]