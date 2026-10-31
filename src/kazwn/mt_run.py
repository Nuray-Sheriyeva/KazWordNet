"""S4.2: run one MT engine over the MT inputs; raw outputs are saved unchanged.

Run (from repo root), smoke test first, then the real run:
  PYTHONPATH=src python -m kazwn.mt_run --engine nllb600m --limit 5
  PYTHONPATH=src python -m kazwn.mt_run --engine nllb600m
Test-pool inputs are refused unless --allow-test is given (only after the engine is frozen).
"""
import argparse, csv, datetime, json, platform, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MT_DIR = ROOT / "data" / "raw" / "mt"
INPUTS = MT_DIR / "inputs.tsv"
CFG = ROOT / "configs" / "mt_engines.json"


def read_inputs(pools, path=INPUTS):
    with open(path, encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f, delimiter="\t") if r["pool"] in pools]


class HFEngine:
    """Hugging Face seq2seq adapter for NLLB-style (nllb) and M2M100-style (m2m100) models."""

    def __init__(self, cfg, device="cpu"):
        import torch, transformers
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, M2M100Tokenizer
        self.torch, self.cfg, self.device = torch, cfg, device
        kw = {"revision": cfg["revision"]} if cfg.get("revision") else {}
        if cfg["family"] == "nllb":
            self.tok = AutoTokenizer.from_pretrained(cfg["model_id"], src_lang=cfg["src"], **kw)
            self.forced = self.tok.convert_tokens_to_ids(cfg["tgt"])
        elif cfg["family"] == "m2m100":
            self.tok = M2M100Tokenizer.from_pretrained(cfg["model_id"], **kw)
            self.tok.src_lang = cfg["src"]
            self.forced = self.tok.get_lang_id(cfg["tgt"])
        else:
            raise ValueError(f"unknown family {cfg['family']!r}")
        self.model = AutoModelForSeq2SeqLM.from_pretrained(cfg["model_id"], **kw).to(device).eval()
        self.meta = {"model_id": cfg["model_id"],
                     "resolved_revision": getattr(self.model.config, "_commit_hash", None),
                     "family": cfg["family"], "src": cfg["src"], "tgt": cfg["tgt"],
                     "num_beams": cfg.get("num_beams", 4), "max_new_tokens": cfg.get("max_new_tokens", 128),
                     "do_sample": False, "device": device, "torch": torch.__version__,
                     "transformers": transformers.__version__, "python": platform.python_version()}

    def translate(self, texts):
        with self.torch.no_grad():
            enc = self.tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=256).to(self.device)
            out = self.model.generate(**enc, forced_bos_token_id=self.forced, do_sample=False,
                                      num_beams=self.meta["num_beams"], max_new_tokens=self.meta["max_new_tokens"])
        return self.tok.batch_decode(out, skip_special_tokens=True)


def run_engine(engine, rows, out_path, batch_size):
    """Translate rows not yet in out_path (resumable). Fixed batching: sort by (length, id)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            done = {json.loads(line)["input_id"] for line in f if line.strip()}
    todo = sorted((r for r in rows if r["input_id"] not in done), key=lambda r: (len(r["text"]), r["input_id"]))
    with open(out_path, "a", encoding="utf-8", newline="\n") as f:
        for i in range(0, len(todo), batch_size):
            batch = todo[i:i + batch_size]
            outs = engine.translate([r["text"] for r in batch])
            for r, o in zip(batch, outs):
                f.write(json.dumps({"input_id": r["input_id"], "synset_id": r["synset_id"],
                                    "lemma_en": r["lemma_en"], "pos": r["pos"], "pool": r["pool"],
                                    "input": r["text"], "output": o}, ensure_ascii=False) + "\n")
            f.flush()
            print(f"  {min(i + batch_size, len(todo))}/{len(todo)}", file=sys.stderr)
    return len(todo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    ap.add_argument("--pools", default="dev,rest")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--batch", type=int)
    ap.add_argument("--limit", type=int, help="smoke test: only the first N inputs, separate output file")
    ap.add_argument("--allow-test", action="store_true")
    a = ap.parse_args()

    pools = set(a.pools.split(","))
    if "test" in pools and not a.allow_test:
        sys.exit("Refusing to run on the test pool. Use --allow-test only after the engine is frozen (S4.5).")
    cfgs = json.loads(CFG.read_text(encoding="utf-8"))
    if a.engine not in cfgs:
        sys.exit(f"Unknown engine {a.engine!r}; known: {sorted(cfgs)}")
    cfg = cfgs[a.engine]
    rows = sorted(read_inputs(pools), key=lambda r: r["input_id"])
    if a.limit:
        rows = rows[:a.limit]
    engine = HFEngine(cfg, a.device)

    meta_path = MT_DIR / f"{a.engine}.meta.json"
    out_path = MT_DIR / (f"{a.engine}.smoke.jsonl" if a.limit else f"{a.engine}.jsonl")
    if not a.limit:
        if meta_path.exists():
            old = json.loads(meta_path.read_text(encoding="utf-8"))
            if old.get("resolved_revision") != engine.meta["resolved_revision"]:
                sys.exit("Model revision differs from the earlier run of this engine; refusing to mix outputs.")
        meta = {**engine.meta, "engine": a.engine, "pools": sorted(pools), "date": datetime.date.today().isoformat()}
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    n = run_engine(engine, rows, out_path, a.batch or cfg.get("batch_size", 16))
    print(f"translated {n} new inputs -> {out_path}")
    if a.limit:
        print(out_path.read_text(encoding="utf-8")[:1500])


if __name__ == "__main__":
    main()