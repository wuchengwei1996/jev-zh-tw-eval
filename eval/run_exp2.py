"""實驗 2：單次題數 Q。每則語句：1 題 choice（scenario）＋(Q-1) 題 noul。
Q = 1,4,8,16,32,64 各送一次；另把同樣 64 題拆成 64 次單題請求。
整個掃描連續跑兩輪（pass 1、pass 2），延遲取兩輪中較低值。另測 65 題是否報錯。
原始結果寫 local-results/A/exp2_raw.jsonl。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, RESULTS, FIXED_ENDPOINT, call, read_jsonl  # noqa: E402

KW = {"env_extra": FIXED_ENDPOINT, "retries": 8}  # 延遲實驗只打 gpu GPU，避免自動換到 Mac 混入延遲

QS = [1, 4, 8, 16, 32, 64]


def qdict(qs):
    out = {}
    for q in qs:
        d = {"type": q["type"], "instructions": q["instructions"]}
        if "criteria" in q:
            d["criteria"] = q["criteria"]
        out[q["key"]] = d
    return out


def main():
    items = read_jsonl(os.path.join(DATA, "exp2_items.jsonl"))
    out = os.path.join(RESULTS, "exp2_raw.jsonl")
    done = set()
    if os.path.exists(out):
        done = {(r["pass"], r["massive_id"], r["mode"], r["Q"], r.get("qkey")) for r in read_jsonl(out)}
    with open(out, "a", encoding="utf-8") as f:
        # 65 題報錯測試（64 題＋複製 1 題換 key）
        it = items[0]
        qs65 = list(it["questions"]) + [dict(it["questions"][1], key="n64")]
        r = call({"state": it["state"], "questions": qdict(qs65)}, **KW)
        f.write(json.dumps({"pass": 0, "massive_id": it["massive_id"], "mode": "q65_error_test", "Q": 65,
                            "exit": r["exit"], "ms": r["ms"], "error": r["data"].get("error")},
                           ensure_ascii=False) + "\n")
        for p in (1, 2):
            for it in items:
                for q in QS:
                    key = (p, it["massive_id"], "batch", q, None)
                    if key in done:
                        continue
                    r = call({"state": it["state"], "questions": qdict(it["questions"][:q])}, **KW)
                    d = r["data"]
                    f.write(json.dumps({"pass": p, "massive_id": it["massive_id"], "mode": "batch", "Q": q,
                                        "qkey": None, "exit": r["exit"], "ms": r["ms"], "retries": r["retries"],
                                        "served_by": d.get("served_by"), "usage": d.get("usage"),
                                        "answers": d.get("answers"), "error": d.get("error")},
                                       ensure_ascii=False) + "\n")
                    f.flush()
                for qq in it["questions"]:
                    key = (p, it["massive_id"], "single", 1, qq["key"])
                    if key in done:
                        continue
                    r = call({"state": it["state"], "questions": qdict([qq])}, **KW)
                    d = r["data"]
                    f.write(json.dumps({"pass": p, "massive_id": it["massive_id"], "mode": "single", "Q": 1,
                                        "qkey": qq["key"], "exit": r["exit"], "ms": r["ms"], "retries": r["retries"],
                                        "served_by": d.get("served_by"), "usage": d.get("usage"),
                                        "answers": d.get("answers"), "error": d.get("error")},
                                       ensure_ascii=False) + "\n")
                    f.flush()
            print("pass", p, "done", flush=True)


if __name__ == "__main__":
    main()
