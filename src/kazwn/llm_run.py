"""B2: run the LLM on one prompt per synset. Logs every prompt and response; stops at the spend cap.

Modes: --preview N (no API), default run, --project TAG (cost rule), --freeze (hash prompt+model before test).
Dev only until the prompt is frozen: test synsets need --allow-test and a matching configs/llm_freeze.json.
"""
import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "configs/llm.json"
FREEZE = ROOT / "configs/llm_freeze.json"
SCOPE = ROOT / "data/scope/scope_1k_frozen.tsv"
DEV = ROOT / "data/eval/eval_dev.tsv"
TEST = ROOT / "data/eval/eval_test.tsv"
RAW = ROOT / "data/raw/llm"
REPORTS = ROOT / "data/reports"

POS_NAME = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective"}
SCHEMA = {
    "type": "object",
    "properties": {"lemmas": {"type": "array", "items": {"type": "string"}}},
    "required": ["lemmas"],
    "additionalProperties": False,
}


class LLMError(Exception):
    pass


def load_cfg(path=CFG):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_tsv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def split_names(s):
    """Split a lemma list from the scope TSV ('|', ';' or ', ' separated); underscores become spaces."""
    s = (s or "").strip()
    if not s:
        return []
    if "|" in s:
        parts = s.split("|")
    elif ";" in s:
        parts = s.split(";")
    elif ", " in s:
        parts = s.split(", ")
    else:
        parts = [s]
    return [p.strip().replace("_", " ") for p in parts if p.strip()]


def build_inputs(scope_rows, dev_ids, test_ids):
    out = []
    for r in scope_rows:
        sid = r["synset_id"]
        out.append({
            "input_id": sid, "synset_id": sid, "pos": r["pos"],
            "lemmas_en": split_names(r["lemmas_en"]), "gloss": r["gloss"],
            "examples": [e.strip() for e in (r.get("examples") or "").split(" || ") if e.strip()],
            "hypernym": split_names(r.get("hypernym_lemmas", "")),
            "pool": "test" if sid in test_ids else "dev" if sid in dev_ids else "rest",
        })
    return out


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_prompt(path):
    text = Path(path).read_text(encoding="utf-8")
    if "### SYSTEM" not in text or "### USER" not in text:
        raise LLMError(f"{path}: missing ### SYSTEM / ### USER markers")
    system = text.split("### SYSTEM", 1)[1].split("### USER", 1)[0].strip()
    user = text.split("### USER", 1)[1].strip()
    return system, user


def render(system, user_t, inp, cfg):
    sysm = system.replace("<<MAX>>", str(cfg["max_lemmas"]))
    user = (user_t.replace("<<POS>>", POS_NAME[inp["pos"]])
            .replace("<<LEMMAS>>", ", ".join(inp["lemmas_en"]))
            .replace("<<GLOSS>>", inp["gloss"])
            .replace("<<EXAMPLES>>", " | ".join(inp["examples"]) or "none")
            .replace("<<HYPERNYM>>", ", ".join(inp["hypernym"]) or "none"))
    return sysm, user


def cost_usd(usage, price):
    return (usage["input_tokens"] * price["in"] + usage["output_tokens"] * price["out"]) / 1e6


def read_raw(path):
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def total_spent(raw_dir=RAW):
    return sum(r.get("cost_usd", 0.0) for p in sorted(Path(raw_dir).glob("*.jsonl")) for r in read_raw(p))


def make_client():
    try:
        import anthropic
    except ImportError:
        raise LLMError("pip install anthropic (and pin the version in requirements.txt)")
    return anthropic.Anthropic(max_retries=3)  # reads ANTHROPIC_API_KEY from the environment


def call_model(client, model, cfg, system, user):
    resp = client.messages.create(
        model=model, max_tokens=cfg["max_tokens"], system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": cfg["effort"], "format": {"type": "json_schema", "schema": SCHEMA}},
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
    return text, usage, resp.stop_reason


def check_freeze(cfg, model, prompt_path, freeze_path=FREEZE):
    if not Path(freeze_path).exists():
        raise LLMError("test pool needs configs/llm_freeze.json: run --freeze first")
    fz = json.loads(Path(freeze_path).read_text(encoding="utf-8"))
    now = {"prompt_sha256": sha256_file(prompt_path), "model": model, "effort": cfg["effort"]}
    for k, v in now.items():
        if fz.get(k) != v:
            raise LLMError(f"freeze mismatch on {k}: frozen {fz.get(k)!r}, current {v!r}")


def select(inputs, pools, limit=None):
    sel = [i for i in inputs if i["pool"] in pools]
    return sel[:limit] if limit else sel


def run(inputs, pools, tag, model_key, cfg, allow_test=False, limit=None, client=None,
        raw_dir=RAW, prompt_path=None, freeze_path=FREEZE, log=print):
    model = cfg[model_key]
    prompt_path = Path(prompt_path or ROOT / cfg["prompt_file"])
    if "test" in pools:
        if not allow_test:
            raise LLMError("test pool blocked: pass --allow-test (only after the prompt is frozen)")
        check_freeze(cfg, model, prompt_path, freeze_path)
    system, user_t = load_prompt(prompt_path)
    sha = sha256_file(prompt_path)
    out = Path(raw_dir) / f"{tag}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    existing = read_raw(out)
    for r in existing:
        if r["model"] != model or r["prompt_sha256"] != sha:
            raise LLMError(f"{out} holds rows from another model/prompt; use a new --tag")
    done = {r["input_id"] for r in existing}
    todo = [i for i in select(inputs, pools, limit) if i["input_id"] not in done]
    spent = total_spent(raw_dir)
    price = cfg["prices_usd_per_mtok"][model]
    client = client or make_client()
    n = 0
    with open(out, "a", encoding="utf-8") as f:
        for inp in todo:
            if spent >= cfg["cap_usd"]:
                log(f"STOP: spend ${spent:.4f} reached cap ${cfg['cap_usd']:.2f}")
                break
            sysm, user = render(system, user_t, inp, cfg)
            text, usage, stop = call_model(client, model, cfg, sysm, user)
            c = cost_usd(usage, price)
            spent += c
            row = {"input_id": inp["input_id"], "synset_id": inp["synset_id"], "pos": inp["pos"],
                   "lemma_en": "|".join(inp["lemmas_en"]), "pool": inp["pool"], "model": model,
                   "effort": cfg["effort"], "prompt_sha256": sha, "system": sysm, "user": user,
                   "response_text": text, "stop_reason": stop, "usage": usage, "cost_usd": c,
                   "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            n += 1
            if n % 10 == 0:
                log(f"{n}/{len(todo)} done, total spent ${spent:.4f}")
    log(f"{n} new rows in {out}; total spent ${spent:.4f} of ${cfg['cap_usd']:.2f}")
    return n, spent


def project(tag, cfg, raw_dir=RAW):
    rows = read_raw(Path(raw_dir) / f"{tag}.jsonl")
    if not rows:
        raise LLMError(f"no rows for tag {tag}")
    if {r["model"] for r in rows} != {cfg["primary"]}:
        raise LLMError("the cost pilot must be run on the primary model")
    p = cfg["projection"]
    mean = sum(r["cost_usd"] for r in rows) / len(rows)
    projected = mean * (p["standard_prompts"] + p["batch_prompts"] * p["batch_discount"])
    return {
        "tag": tag, "model": cfg["primary"], "pilot_rows": len(rows),
        "mean_input_tokens": sum(r["usage"]["input_tokens"] for r in rows) / len(rows),
        "mean_output_tokens": sum(r["usage"]["output_tokens"] for r in rows) / len(rows),
        "mean_cost_usd": mean, "projected_total_usd": projected, "cap_usd": cfg["cap_usd"],
        "rule": "projected = mean cost x (standard + batch x discount) prompts; primary if <= cap else fallback",
        "decision": cfg["primary"] if projected <= cfg["cap_usd"] else cfg["fallback"],
    }


def freeze(cfg, model_key, prompt_path=None, freeze_path=FREEZE):
    if Path(freeze_path).exists():
        raise LLMError(f"{freeze_path} already exists; a change needs a dated amendment, not an overwrite")
    prompt_path = Path(prompt_path or ROOT / cfg["prompt_file"])
    fz = {"prompt_file": str(Path(cfg["prompt_file"])), "prompt_sha256": sha256_file(prompt_path),
          "model": cfg[model_key], "effort": cfg["effort"], "max_tokens": cfg["max_tokens"],
          "date": date.today().isoformat()}
    Path(freeze_path).write_text(json.dumps(fz, indent=2), encoding="utf-8")
    return fz


def load_inputs():
    ids = lambda p: {r["synset_id"] for r in read_tsv(p)}
    return build_inputs(read_tsv(SCOPE), ids(DEV), ids(TEST))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", help="output name: data/raw/llm/<tag>.jsonl")
    ap.add_argument("--pools", default="dev")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--model", choices=["primary", "fallback"], default="primary")
    ap.add_argument("--allow-test", action="store_true")
    ap.add_argument("--preview", type=int, metavar="N", help="print N rendered prompts, no API call")
    ap.add_argument("--project", metavar="TAG", help="apply the cost rule to a pilot run")
    ap.add_argument("--freeze", action="store_true")
    a = ap.parse_args(argv)
    cfg = load_cfg()
    try:
        if a.freeze:
            print(json.dumps(freeze(cfg, a.model), indent=2))
        elif a.project:
            rep = project(a.project, cfg)
            REPORTS.mkdir(parents=True, exist_ok=True)
            (REPORTS / "llm_cost_projection.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
            print(json.dumps(rep, indent=2))
        elif a.preview:
            system, user_t = load_prompt(ROOT / cfg["prompt_file"])
            pools = set(a.pools.split(","))
            sel = select(load_inputs(), pools, a.preview)
            print("=== SYSTEM ===\n" + render(system, user_t, sel[0], cfg)[0])
            for inp in sel:
                print(f"\n=== USER ({inp['input_id']}, {inp['pool']}) ===\n" + render(system, user_t, inp, cfg)[1])
        else:
            if not a.tag:
                raise LLMError("--tag is required for a run")
            run(load_inputs(), set(a.pools.split(",")), a.tag, a.model, cfg, a.allow_test, a.limit)
    except LLMError as e:
        print(f"FAILED: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())