"""抽題：所有實驗的題目檔（jev eval 相容格式：{id,type,state,instructions,criteria,expected}）。
亂數種子固定 42。標準答案一律取資料集的人工標註。"""
import csv
import io
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, INTENTS, load_desc, write_jsonl, read_jsonl  # noqa: E402

DESC = load_desc()
SCEN = sorted(DESC["scenarios"])
assert len(INTENTS) == 60 and len(SCEN) == 18
INS_INTENT_ZH = "這句話是使用者對語音助理說的話。它的意圖是哪一個？"
INS_INTENT_EN = "This is something a speaker said to a voice assistant. Which intent is it?"
INS_SCEN_ZH = "這句話是使用者對語音助理說的話。它屬於哪個情境？"
NS = [2, 4, 8, 12, 16, 20, 26]


def scen_of(intent):
    return intent.split("_")[0]


def massive(lang):
    return {r["id"]: r for r in read_jsonl(os.path.join(DATA, "source_massive_%s_test.jsonl" % lang))}


def item_rng(tag, mid):
    return random.Random("42:%s:%s" % (tag, mid))


def crit(names, kind, with_desc):
    d = DESC["intents" if kind == "intent" else "scenarios"]
    return {n: (d[n] if with_desc else "") for n in names}


def options_for(mid, gold, n):
    """巢狀干擾項：每題固定一個其他 59 個 intent 的亂序，N 取前 N-1 個；選項順序再洗一次。"""
    r = item_rng("distractors", mid)
    perm = [i for i in INTENTS if i != gold]
    r.shuffle(perm)
    opts = [gold] + perm[:n - 1]
    r2 = item_rng("order%d" % n, mid)
    r2.shuffle(opts)
    return opts


def main():
    tw, cn, en = massive("zh-TW"), massive("zh-CN"), massive("en")
    ids = sorted(tw, key=int)

    # ── 實驗 1：選項數 N（zh-TW，100 題，每個 N 同一批題目）
    s1 = random.Random(42).sample(ids, 100)
    write_jsonl(os.path.join(DATA, "exp1_sample_ids.jsonl"), [{"massive_id": i} for i in s1])
    for n in NS + [27]:
        for wd in (False, True):
            rows = []
            for mid in s1:
                g = tw[mid]["label"]
                opts = options_for(mid, g, n)  # n=27 用來驗證超限報錯
                rows.append({"id": "e1-n%d-%s-%s" % (n, "desc" if wd else "name", mid), "type": "choice",
                             "state": tw[mid]["text"], "instructions": INS_INTENT_ZH,
                             "criteria": crit(opts, "intent", wd), "expected": g, "massive_id": mid})
            write_jsonl(os.path.join(DATA, "exp1_N%d_%s.jsonl" % (n, "desc" if wd else "name")), rows)
    # 兩段式第一段：18 選 1 scenario（第二段依第一段結果在執行時組題）
    for wd in (False, True):
        rows = [{"id": "e1-stage1-%s-%s" % ("desc" if wd else "name", mid), "type": "choice",
                 "state": tw[mid]["text"], "instructions": INS_SCEN_ZH,
                 "criteria": crit(SCEN, "scenario", wd), "expected": scen_of(tw[mid]["label"]),
                 "massive_id": mid, "gold_intent": tw[mid]["label"]} for mid in s1]
        write_jsonl(os.path.join(DATA, "exp1_twostage_stage1_%s.jsonl" % ("desc" if wd else "name")), rows)
    # 淘汰賽分組：60 個 intent 固定亂序後切 3 組各 20
    g = list(INTENTS)
    random.Random(42).shuffle(g)
    groups = [sorted(g[0:20]), sorted(g[20:40]), sorted(g[40:60])]
    json.dump({"groups": groups}, open(os.path.join(DATA, "exp1_knockout_groups.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ── 實驗 2：單次題數 Q（zh-TW，30 則語句，每則 64 題的固定順序題庫）
    s2 = random.Random(42).sample(ids, 30)
    rows = []
    for mid in s2:
        gi = tw[mid]["label"]
        gs = scen_of(gi)
        pool_neg = [("intent", i) for i in INTENTS if i != gi] + [("scenario", s) for s in SCEN if s != gs]
        item_rng("q-pool", mid).shuffle(pool_neg)
        pool = [("intent", gi), ("scenario", gs)] + pool_neg[:61]
        qs = [{"key": "c00", "type": "choice", "instructions": INS_SCEN_ZH,
               "criteria": crit(SCEN, "scenario", True), "expected": gs}]
        for k, (kind, name) in enumerate(pool, 1):
            if kind == "intent":
                ins = "這句話是使用者對語音助理說的話。它的意圖是否為「%s」（%s）？" % (name, DESC["intents"][name])
                exp = name == gi
            else:
                ins = "這句話是使用者對語音助理說的話。它是否屬於「%s」情境（%s）？" % (name, DESC["scenarios"][name])
                exp = name == gs
            qs.append({"key": "n%02d" % k, "type": "noul", "instructions": ins, "expected": exp,
                       "label_kind": kind, "label": name})
        assert len(qs) == 64
        rows.append({"massive_id": mid, "state": tw[mid]["text"], "gold_intent": gi, "gold_scenario": gs,
                     "questions": qs})
    write_jsonl(os.path.join(DATA, "exp2_items.jsonl"), rows)

    # ── 實驗 3：語言（同一批平行語句 120 題，N=8，選項與順序三語完全相同）
    s3 = random.Random(42).sample(ids, 120)
    for lang, src in (("zh-TW", tw), ("zh-CN", cn), ("en-US", en)):
        for ins_name, ins in (("insZH", INS_INTENT_ZH), ("insEN", INS_INTENT_EN)):
            out = []
            for mid in s3:
                gl = tw[mid]["label"]
                assert src[mid]["label"] == gl
                out.append({"id": "e3-%s-%s-%s" % (lang, ins_name, mid), "type": "choice",
                            "state": src[mid]["text"], "instructions": ins,
                            "criteria": crit(options_for(mid, gl, 8), "intent", False), "expected": gl,
                            "massive_id": mid})
            write_jsonl(os.path.join(DATA, "exp3_%s_%s.jsonl" % (lang, ins_name)), out)

    print("MASSIVE generated:", len(s1), len(s2), len(s3))


if __name__ == "__main__":
    main()
