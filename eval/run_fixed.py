"""逐題用 `jev ask -` 跑固定題目檔（每次請求 1 題），原始結果寫 local-results/A/<檔名>.raw.jsonl。
用法：python3 run_fixed.py data/exp1_N8_name.jsonl [...] [--limit N]"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import RESULTS, call, read_jsonl  # noqa: E402


def run_file(path, limit=None):
    items = read_jsonl(path)
    if limit:
        items = items[:limit]
    name = os.path.basename(path).replace(".jsonl", "")
    out = os.path.join(RESULTS, name + ".raw.jsonl")
    done = {}
    if os.path.exists(out):
        done = {r["id"]: r for r in read_jsonl(out)}
    with open(out, "a", encoding="utf-8") as f:
        for it in items:
            if it["id"] in done:
                continue
            q = {"type": it["type"], "instructions": it["instructions"]}
            if "criteria" in it:
                q["criteria"] = it["criteria"]
            res = call({"state": it["state"], "questions": {"q": q}})
            d = res["data"]
            rec = {"id": it["id"], "expected": it["expected"], "exit": res["exit"], "ms": res["ms"],
                   "served_by": d.get("served_by"), "usage": d.get("usage"),
                   "answer": (d.get("answers") or {}).get("q"),
                   "error": d.get("error"), "detail": d.get("detail")}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
    print(name, "done", len(items))


if __name__ == "__main__":
    args = sys.argv[1:]
    limit = None
    if "--limit" in args:
        i = args.index("--limit")
        limit = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    for p in args:
        run_file(p, limit)
