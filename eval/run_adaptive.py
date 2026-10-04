"""實驗 1 的「類別 > 26」策略：兩段式（scenario→intent，top1／top2）與淘汰賽（3 組各 20 → 決賽）。
第一段結果來自 local-results/A/exp1_twostage_stage1_<v>.raw.jsonl（run_fixed.py 產生）。
原始結果寫 local-results/A/exp1_adaptive_<策略>_<v>.raw.jsonl。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, INTENTS, RESULTS, FIXED_ENDPOINT, call, load_desc, read_jsonl  # noqa: E402

DESC = load_desc()
INS_INTENT_ZH = "這句話是使用者對語音助理說的話。它的意圖是哪一個？"


def crit(names, wd):
    return {n: (DESC["intents"][n] if wd else "") for n in names}


def ask_choice(state, names, wd):
    res = call({"state": state, "questions": {"q": {"type": "choice", "instructions": INS_INTENT_ZH,
                                                     "criteria": crit(names, wd)}}},
               env_extra=FIXED_ENDPOINT, retries=8)  # 只打 gpu，延遲才可比
    d = res["data"]
    return {"exit": res["exit"], "ms": res["ms"], "served_by": d.get("served_by"),
            "answer": (d.get("answers") or {}).get("q"), "error": d.get("error"), "options": names}


def resume(out):
    return {r["id"] for r in read_jsonl(out)} if os.path.exists(out) else set()


def twostage(v):
    wd = v == "desc"
    st1 = {r["id"]: r for r in read_jsonl(os.path.join(RESULTS, "exp1_twostage_stage1_%s.raw.jsonl" % v))}
    items = read_jsonl(os.path.join(DATA, "exp1_twostage_stage1_%s.jsonl" % v))
    for mode in ("top1", "top2"):
        out = os.path.join(RESULTS, "exp1_adaptive_twostage-%s_%s.raw.jsonl" % (mode, v))
        done = resume(out)
        with open(out, "a", encoding="utf-8") as f:
            for it in items:
                rid = "%s-%s" % (mode, it["massive_id"])
                if rid in done:
                    continue
                s1 = st1[it["id"]]
                probs = s1["answer"]["probabilities"]
                ranked = sorted(probs, key=lambda k: -probs[k])
                scen = ranked[:1] if mode == "top1" else ranked[:2]
                opts = sorted(i for i in INTENTS if i.split("_")[0] in scen)
                rec = {"id": rid, "massive_id": it["massive_id"], "expected": it["gold_intent"],
                       "stage1": {"choice": ranked[0], "top": scen, "p": [probs[s] for s in scen],
                                  "ms": s1["ms"], "expected": it["expected"],
                                  "served_by": s1.get("served_by")}}
                if len(opts) == 1:
                    rec.update({"final": opts[0], "stage2": None, "conf": probs[scen[0]],
                                "ms_total": s1["ms"]})
                else:
                    a = ask_choice(it["state"], opts, wd)
                    pmax = max(a["answer"]["probabilities"].values())
                    rec.update({"final": a["answer"]["choice"], "stage2": a,
                                "conf": sum(probs[s] for s in scen) * pmax,
                                "ms_total": s1["ms"] + a["ms"]})
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
        print("twostage", mode, v, "done")


def knockout(v):
    wd = v == "desc"
    groups = json.load(open(os.path.join(DATA, "exp1_knockout_groups.json"), encoding="utf-8"))["groups"]
    items = read_jsonl(os.path.join(DATA, "exp1_twostage_stage1_%s.jsonl" % v))
    out = os.path.join(RESULTS, "exp1_adaptive_knockout_%s.raw.jsonl" % v)
    done = resume(out)
    with open(out, "a", encoding="utf-8") as f:
        for it in items:
            rid = "ko-%s" % it["massive_id"]
            if rid in done:
                continue
            rounds = [ask_choice(it["state"], g, wd) for g in groups]
            winners = [r["answer"]["choice"] for r in rounds]
            wp = {r["answer"]["choice"]: max(r["answer"]["probabilities"].values()) for r in rounds}
            fin = ask_choice(it["state"], winners, wd)
            pick = fin["answer"]["choice"]
            rec = {"id": rid, "massive_id": it["massive_id"], "expected": it["gold_intent"],
                   "group_winners": winners, "gold_won_group": it["gold_intent"] in winners,
                   "final": pick, "final_answer": fin["answer"],
                   "conf": wp[pick] * max(fin["answer"]["probabilities"].values()),
                   "ms_total": sum(r["ms"] for r in rounds) + fin["ms"],
                   "served_by": [r["served_by"] for r in rounds] + [fin["served_by"]]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
    print("knockout", v, "done")


if __name__ == "__main__":
    for v in ("name", "desc"):
        twostage(v)
        knockout(v)
