"""彙整所有原始結果 → results/summary.json 與 results/tables.txt。"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, RESULTS, maxprob, percentile, read_jsonl, summarize  # noqa: E402

OUT = {}
T = []


def P(s=""):
    T.append(s)


def load(name):
    p = os.path.join(RESULTS, name + ".raw.jsonl")
    return read_jsonl(p) if os.path.exists(p) else []


def fmt(x, pct=False):
    if x is None:
        return "-"
    return ("%.1f%%" % (x * 100)) if pct else ("%g" % x)


def row(label, s, extra=""):
    if not s.get("n"):
        return "%-28s (無資料)" % label
    ci = s.get("acc_ci95") or [None, None]
    acc = "%s[%s–%s]" % (fmt(s["accuracy"], True), fmt(ci[0], True), fmt(ci[1], True))
    return ("%-28s n=%-4d 準確度=%-22s ECE=%-7s 高信心錯(全體)=%-6s 高信心錯(≥0.9中)=%-6s(≥0.9 共%s題) 平均信心=%-6s p50=%-7s p95=%-7s %s"
            % (label, s["n"], acc, fmt(s["ece"]), fmt(s["hiconf_wrong_of_all"], True),
               fmt(s["hiconf_wrong_of_hiconf"], True), s.get("hiconf_n"), fmt(s["mean_conf"]), fmt(s.get("lat_ms_p50")),
               fmt(s.get("lat_ms_p95")), extra))


def fixed_stats(rs, kind="choice"):
    ok_rs = [r for r in rs if r["exit"] == 0 and r.get("answer")]
    pairs, lat, tok = [], [], []
    for r in ok_rs:
        a = r["answer"]
        if kind == "choice":
            ok = a.get("choice") == r["expected"]
        else:
            probs = a["probabilities"]
            ok = int(max(probs, key=lambda k: probs[k])) == int(r["expected"])
        pairs.append((maxprob(a), ok))
        if r.get("served_by") == os.environ.get("JEV_LATENCY_ENDPOINT", "local"):  # 延遲只算 gpu GPU 回答的請求
            lat.append(r["ms"])
        if r.get("usage"):
            tok.append(r["usage"].get("input_tokens", 0))
    s = summarize(pairs, lat)
    s["failures"] = len(rs) - len(ok_rs)
    s["served_by"] = dict(collections.Counter(r.get("served_by") for r in rs))
    s["mean_input_tokens"] = round(sum(tok) / len(tok), 1) if tok else None
    return s


def scen(i):
    return i.split("_")[0]


def exp1():
    P("=" * 100)
    P("維度 1：選項數 N（MASSIVE zh-TW test，100 則語句，每個 N 同一批；選項＝正確 intent＋N-1 個隨機干擾 intent）")
    P("=" * 100)
    res = {}
    for v, vname in (("name", "只給英文 intent 名"), ("desc", "名稱＋繁中描述")):
        P("-- %s --" % vname)
        for n in (2, 4, 8, 12, 16, 20, 26):
            rs = load("exp1_N%d_%s" % (n, v))
            s = fixed_stats(rs)
            # 錯誤中「選到同 scenario 的干擾項」比例
            wrong = [r for r in rs if r.get("answer") and r["answer"].get("choice") != r["expected"]]
            same = sum(1 for r in wrong if scen(r["answer"]["choice"]) == scen(r["expected"]))
            s["wrong_same_scenario"] = same
            s["wrong_total"] = len(wrong)
            s["chance"] = round(1 / n, 4)
            res["N%d_%s" % (n, v)] = s
            P(row("N=%d" % n, s, "隨機猜=%.1f%% tokens≈%s 錯誤中同scenario=%d/%d 失敗=%d served=%s"
                  % (100 / n, s["mean_input_tokens"], same, len(wrong), s["failures"], s["served_by"])))
    # 成對比較 desc vs name
    P("-- 描述的影響（同一題成對比較：name 錯→desc 對 / name 對→desc 錯）--")
    for n in (2, 4, 8, 12, 16, 20, 26):
        a = {r["id"].split("-")[-1]: r for r in load("exp1_N%d_name" % n)}
        b = {r["id"].split("-")[-1]: r for r in load("exp1_N%d_desc" % n)}
        fix = brk = 0
        for k in a:
            if k in b and a[k].get("answer") and b[k].get("answer"):
                oa = a[k]["answer"]["choice"] == a[k]["expected"]
                ob = b[k]["answer"]["choice"] == b[k]["expected"]
                fix += (not oa) and ob
                brk += oa and (not ob)
        res["N%d_pair" % n] = {"name_wrong_desc_right": fix, "name_right_desc_wrong": brk}
        P("N=%-3d desc 救回 %d 題、desc 弄錯 %d 題" % (n, fix, brk))
    # N=27
    for v in ("name", "desc"):
        rs = load("exp1_N27_%s" % v)
        res["N27_%s" % v] = [{"exit": r["exit"], "error": r["error"]} for r in rs]
        P("N=27 (%s)：%d 次請求，exit code=%s，訊息=%s" % (v, len(rs), sorted({r["exit"] for r in rs}),
                                                   rs[0]["error"] if rs else "-"))
    # 類別 > 26：兩段式與淘汰賽
    P("-- 類別 60 個（> 26）的處理策略（同 100 則語句；信心＝各段最高機率連乘，延遲＝各段相加）--")
    for v in ("name", "desc"):
        st1 = fixed_stats(load("exp1_twostage_stage1_%s" % v))
        res["stage1_%s" % v] = st1
        P(row("第一段 scenario 18 選 1 (%s)" % v, st1))
        for strat in ("twostage-top1", "twostage-top2", "knockout"):
            rs = load("exp1_adaptive_%s_%s" % (strat, v))
            if not rs:
                continue
            pairs = [(r["conf"], r["final"] == r["expected"]) for r in rs]

            def all_wh(r):
                hosts = list(r.get("served_by") or [])
                if r.get("stage1"):
                    hosts.append(r["stage1"].get("served_by"))
                if r.get("stage2"):
                    hosts.append(r["stage2"].get("served_by"))
                return all(h == os.environ.get("JEV_LATENCY_ENDPOINT", "local") for h in hosts)
            lat = [r["ms_total"] for r in rs if all_wh(r)]
            s = summarize(pairs, lat)
            if strat == "knockout":
                s["calls_per_item"] = 4
                s["gold_won_group"] = sum(1 for r in rs if r["gold_won_group"])
                extra = "呼叫數/題=4  正解在分組賽勝出=%d/%d" % (s["gold_won_group"], len(rs))
            else:
                calls = [1 + (1 if r.get("stage2") else 0) for r in rs]
                s["calls_per_item"] = round(sum(calls) / len(calls), 2)
                s["stage1_top_contains_gold"] = sum(1 for r in rs if scen(r["expected"]) in r["stage1"]["top"])
                extra = "呼叫數/題=%.2f  第一段候選含正解 scenario=%d/%d" % (s["calls_per_item"],
                                                                     s["stage1_top_contains_gold"], len(rs))
            res["%s_%s" % (strat, v)] = s
            P(row("%s (%s)" % (strat, v), s, extra))
        P(row("對照：直接 N=26 (%s)" % v, res["N26_%s" % v], "（只有 26 類，非全部 60 類）"))
    OUT["exp1"] = res


def exp2():
    P("")
    P("=" * 100)
    P("維度 2：單次題數 Q（MASSIVE zh-TW test 30 則語句；1 題 choice 選 scenario＋(Q-1) 題 noul「是否屬於 X 類」）")
    P("延遲＝兩輪掃描中較低值（同一請求）；n 為題目數")
    P("=" * 100)
    items = {it["massive_id"]: it for it in read_jsonl(os.path.join(DATA, "exp2_items.jsonl"))}
    raw = read_jsonl(os.path.join(RESULTS, "exp2_raw.jsonl")) if os.path.exists(
        os.path.join(RESULTS, "exp2_raw.jsonl")) else []
    res = {}
    err = [r for r in raw if r["mode"] == "q65_error_test"]
    if err:
        res["q65"] = {"exit": err[-1]["exit"], "error": err[-1]["error"]}
        P("65 題：exit=%s 訊息=%s" % (err[-1]["exit"], err[-1]["error"]))
    # 以 (mid, mode, Q, qkey) 聚合兩輪
    agg = collections.defaultdict(list)
    for r in raw:
        if r["mode"] in ("batch", "single"):
            agg[(r["massive_id"], r["mode"], r["Q"], r.get("qkey"))].append(r)
    failures = sum(1 for r in raw if r["mode"] in ("batch", "single") and r["exit"] != 0)
    res["failures"] = failures
    res["served_by"] = dict(collections.Counter(r.get("served_by") for r in raw if r["mode"] in ("batch", "single")))
    # 兩輪答案是否完全相同（決定性）
    det_diff = 0
    for k, rs in agg.items():
        if len(rs) == 2 and rs[0].get("answers") and rs[1].get("answers"):
            if json.dumps(rs[0]["answers"], sort_keys=True) != json.dumps(rs[1]["answers"], sort_keys=True):
                det_diff += 1
    res["pass1_vs_pass2_answer_diff_requests"] = det_diff

    def answers_of(rs):
        for r in rs:
            if r.get("answers"):
                return r["answers"]
        return None

    def minms(rs):
        ms = [r["ms"] for r in rs if r["exit"] == 0]
        return min(ms) if ms else None

    single_ans = {}
    for (mid, mode, q, key), rs in agg.items():
        if mode == "single":
            a = answers_of(rs)
            if a:
                single_ans[(mid, key)] = a[key]
    P("%-6s %-26s %-36s %-34s %-12s %-14s %-12s %s" % ("Q", "choice 準確度", "noul 準確度（正例召回／負例正確）",
                                                       "全部題 ECE／高信心錯(全體)", "每次延遲p50", "每次延遲p95",
                                                       "每題ms p50", "tokens 平均"))
    for q in (1, 4, 8, 16, 32, 64):
        cp, npairs, pos, neg, lat, perq, tok = [], [], [], [], [], [], []
        for mid, it in items.items():
            rs = agg.get((mid, "batch", q, None))
            if not rs:
                continue
            a = answers_of(rs)
            m = minms(rs)
            if a is None or m is None:
                continue
            lat.append(m)
            perq.append(m / q)
            u = next((r["usage"] for r in rs if r.get("usage")), None)
            if u:
                tok.append(u["input_tokens"])
            for qq in it["questions"][:q]:
                ans = a[qq["key"]]
                if qq["type"] == "choice":
                    cp.append((maxprob(ans), ans["choice"] == qq["expected"]))
                else:
                    ok = (ans["noul"] >= 0.5) == qq["expected"]
                    npairs.append((maxprob(ans), ok))
                    (pos if qq["expected"] else neg).append(ok)
        sc, sn = summarize(cp), summarize(npairs)
        sall = summarize(cp + npairs, lat)
        res["Q%d" % q] = {"choice": sc, "noul": sn, "all": sall,
                          "noul_pos_recall": round(sum(pos) / len(pos), 4) if pos else None,
                          "noul_neg_acc": round(sum(neg) / len(neg), 4) if neg else None,
                          "n_pos": len(pos), "n_neg": len(neg),
                          "lat_ms_p50": sall.get("lat_ms_p50"), "lat_ms_p95": sall.get("lat_ms_p95"),
                          "per_question_ms_p50": round(percentile(perq, 0.5), 1) if perq else None,
                          "mean_input_tokens": round(sum(tok) / len(tok), 1) if tok else None,
                          "max_input_tokens": max(tok) if tok else None}
        R = res["Q%d" % q]
        P("%-6s %-26s %-36s %-34s %-12s %-14s %-12s %s/%s" % (
            q, "%s (n=%d)" % (fmt(sc.get("accuracy"), True), sc.get("n", 0)),
            "%s (n=%d)；%s／%s" % (fmt(sn.get("accuracy"), True), sn.get("n", 0),
                                 fmt(R["noul_pos_recall"], True), fmt(R["noul_neg_acc"], True)) if sn.get("n") else "-",
            "%s／%s" % (fmt(sall.get("ece")), fmt(sall.get("hiconf_wrong_of_all"), True)),
            fmt(R["lat_ms_p50"]), fmt(R["lat_ms_p95"]), fmt(R["per_question_ms_p50"]),
            R["mean_input_tokens"], R["max_input_tokens"]))
    # 分 64 次各 1 題（單題模式）的準確度，與 batch 同一批題目比較
    cp, npairs, pos, neg = [], [], [], []
    for mid, it in items.items():
        for qq in it["questions"]:
            ans = single_ans.get((mid, qq["key"]))
            if not ans:
                continue
            if qq["type"] == "choice":
                cp.append((maxprob(ans), ans["choice"] == qq["expected"]))
            else:
                ok = (ans["noul"] >= 0.5) == qq["expected"]
                npairs.append((maxprob(ans), ok))
                (pos if qq["expected"] else neg).append(ok)
    sc, sn = summarize(cp), summarize(npairs)
    res["single_mode"] = {"choice": sc, "noul": sn, "all": summarize(cp + npairs),
                          "noul_pos_recall": round(sum(pos) / len(pos), 4) if pos else None,
                          "noul_neg_acc": round(sum(neg) / len(neg), 4) if neg else None}
    R = res["single_mode"]
    P("單題模式（64 題各自單獨送）：choice %s (n=%d)；noul %s (n=%d)，正例召回 %s／負例正確 %s；ECE %s；高信心錯 %s" % (
        fmt(sc.get("accuracy"), True), sc.get("n", 0), fmt(sn.get("accuracy"), True), sn.get("n", 0),
        fmt(R["noul_pos_recall"], True), fmt(R["noul_neg_acc"], True), fmt(R["all"].get("ece")),
        fmt(R["all"].get("hiconf_wrong_of_all"), True)))
    # 固定題組（c00、n01、n02、n03：每個 Q≥4 都有）在不同 Q 的答對數，排除題目組成差異
    common = {}
    for q in (4, 8, 16, 32, 64, "single"):
        ok = collections.Counter()
        for mid, it in items.items():
            for qq in it["questions"][:4]:
                if q == "single":
                    x = single_ans.get((mid, qq["key"]))
                else:
                    rs = agg.get((mid, "batch", q, None))
                    a = answers_of(rs) if rs else None
                    x = a[qq["key"]] if a else None
                if x is None:
                    continue
                ok[qq["key"]] += (x["choice"] == qq["expected"]) if qq["type"] == "choice" else (
                    (x["noul"] >= 0.5) == qq["expected"])
        common[str(q)] = dict(ok)
        P("固定題組 Q=%s：答對 c00(choice)=%d n01(正解intent)=%d n02(正解scenario)=%d n03(負例)=%d（各 /%d）" % (
            q, ok["c00"], ok["n01"], ok["n02"], ok["n03"], len(items)))
    res["common_subset_correct"] = common
    # 一致性：batch Q 的每題 vs 單題請求
    P("-- 一致性：同一題在 batch（Q 題一起）與單題請求的答案比較 --")
    cons = {}
    for q in (4, 8, 16, 32, 64):
        same_choice = n_choice = same_side = n_noul = 0
        diffs = []
        for mid, it in items.items():
            rs = agg.get((mid, "batch", q, None))
            a = answers_of(rs) if rs else None
            if not a:
                continue
            for qq in it["questions"][:q]:
                s = single_ans.get((mid, qq["key"]))
                if not s:
                    continue
                b = a[qq["key"]]
                if qq["type"] == "choice":
                    n_choice += 1
                    same_choice += b["choice"] == s["choice"]
                    diffs += [abs(b["probabilities"][k] - s["probabilities"][k]) for k in s["probabilities"]]
                else:
                    n_noul += 1
                    same_side += (b["noul"] >= 0.5) == (s["noul"] >= 0.5)
                    diffs.append(abs(b["noul"] - s["noul"]))
        cons["Q%d" % q] = {"choice_same": same_choice, "choice_n": n_choice, "noul_same_side": same_side,
                           "noul_n": n_noul, "mean_abs_dp": round(sum(diffs) / len(diffs), 5) if diffs else None,
                           "max_abs_dp": round(max(diffs), 5) if diffs else None}
        c = cons["Q%d" % q]
        P("Q=%-3d choice 同答 %d/%d；noul 同側(≥0.5) %d/%d；|Δ機率| 平均 %s、最大 %s" % (
            q, c["choice_same"], c["choice_n"], c["noul_same_side"], c["noul_n"], c["mean_abs_dp"], c["max_abs_dp"]))
    res["consistency_vs_single"] = cons
    # 總耗時：一次 64 題 vs 分 64 次
    t64, t1x64 = [], []
    for mid, it in items.items():
        rs = agg.get((mid, "batch", 64, None))
        m = minms(rs) if rs else None
        singles = [minms(agg.get((mid, "single", 1, qq["key"]), [])) for qq in it["questions"]]
        if m is None or any(x is None for x in singles):
            continue
        t64.append(m)
        t1x64.append(sum(singles))
    if t64:
        res["batch64_vs_64singles"] = {
            "items": len(t64), "batch64_total_ms": round(sum(t64), 1), "singles_total_ms": round(sum(t1x64), 1),
            "batch64_p50_ms": round(percentile(t64, 0.5), 1), "singles_sum_p50_ms": round(percentile(t1x64, 0.5), 1),
            "speedup": round(sum(t1x64) / sum(t64), 2)}
        b = res["batch64_vs_64singles"]
        P("一次 64 題 vs 分 64 次各 1 題（%d 則語句）：每則 p50 %s ms vs %s ms；總計 %.1f s vs %.1f s；快 %.2f 倍" % (
            b["items"], b["batch64_p50_ms"], b["singles_sum_p50_ms"], b["batch64_total_ms"] / 1000,
            b["singles_total_ms"] / 1000, b["speedup"]))
    # 單題請求延遲（CLI 牆鐘，含行程啟動）
    sl = [minms(rs) for (mid, mode, q, key), rs in agg.items() if mode == "single"]
    sl = [x for x in sl if x is not None]
    if sl:
        res["single_call_ms_p50"] = round(percentile(sl, 0.5), 1)
        res["single_call_ms_p95"] = round(percentile(sl, 0.95), 1)
        P("單題請求延遲 p50=%s ms p95=%s ms（n=%d）" % (res["single_call_ms_p50"], res["single_call_ms_p95"], len(sl)))
    P("兩輪答案不同的請求數：%d；失敗請求數：%d；served_by=%s" % (det_diff, failures, res["served_by"]))
    OUT["exp2"] = res


def exp3():
    P("")
    P("=" * 100)
    P("維度 3：語言（MASSIVE 同一批 120 則平行語句；choice N=8，選項與順序三語相同，只給英文 intent 名）")
    P("=" * 100)
    res = {}
    for ins, iname in (("insZH", "繁中題目說明"), ("insEN", "英文題目說明")):
        P("-- %s --" % iname)
        per = {}
        for lang in ("zh-TW", "zh-CN", "en-US"):
            rs = load("exp3_%s_%s" % (lang, ins))
            s = fixed_stats(rs)
            res["%s_%s" % (lang, ins)] = s
            per[lang] = {r["id"].split("-")[-1]: (r["answer"] or {}).get("choice") == r["expected"] for r in rs}
            P(row(lang, s, "tokens≈%s 失敗=%d served=%s" % (s["mean_input_tokens"], s["failures"], s["served_by"])))
        if all(per.values()):
            ks = set.intersection(*[set(v) for v in per.values()])
            all3 = sum(1 for k in ks if all(per[l][k] for l in per))
            none3 = sum(1 for k in ks if not any(per[l][k] for l in per))
            res["overlap_%s" % ins] = {"all_correct": all3, "all_wrong": none3, "n": len(ks)}
            P("三語都對 %d、三語都錯 %d（共 %d）" % (all3, none3, len(ks)))
    OUT["exp3"] = res


def _rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    R = [0.0] * len(v)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for t in range(i, j + 1):
            R[o[t]] = (i + j) / 2
        i = j + 1
    return R


def spearman(x, y):
    rx, ry = _rank(x), _rank(y)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = sum((a - mx) ** 2 for a in rx) ** 0.5
    sy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / sx / sy if sx and sy else None


def exp4():
    P("")
    P("=" * 100)
    P("維度 4：score 刻度數（EmoBank 句子，人工 Valence 1–5 平均分等寬切 k 級；同一批 133 句，依 5 級分層抽樣）")
    P("=" * 100)
    res = {}
    for k in (3, 5, 10):
        rs = load("exp4_score_k%d" % k)
        s = fixed_stats(rs, kind="score")
        ok = [r for r in rs if r["exit"] == 0 and r.get("answer")]
        within1 = abs_err = 0
        for r in ok:
            pr = r["answer"]["probabilities"]
            best = int(max(pr, key=lambda x: pr[x]))
            within1 += abs(best - int(r["expected"])) <= 1
            abs_err += abs(best - int(r["expected"]))
        pred = collections.Counter()
        conf = collections.Counter()
        for r in ok:
            pr = r["answer"]["probabilities"]
            b = int(max(pr, key=lambda x: pr[x]))
            pred[b] += 1
            conf["%d>%d" % (int(r["expected"]), b)] += 1
        val = {x["id"]: x["valence"] for x in read_jsonl(os.path.join(DATA, "exp4_score_k%d.jsonl" % k))}
        rho = spearman([val[r["id"]] for r in ok], [float(r["answer"]["score"]) for r in ok]) if ok else None
        cnt = collections.Counter(int(r["expected"]) for r in ok)
        maj = cnt.most_common(1)[0][0] if cnt else None
        base_exact = cnt[maj] / len(ok) if ok else None
        base_w1 = sum(v for c, v in cnt.items() if abs(c - maj) <= 1) / len(ok) if ok else None
        s.update({"within1": round(within1 / len(ok), 4) if ok else None,
                  "mae_levels": round(abs_err / len(ok), 3) if ok else None,
                  "mae_normalized": round(abs_err / len(ok) / (k - 1), 3) if ok else None,
                  "baseline_majority_exact": round(base_exact, 4) if ok else None,
                  "baseline_majority_within1": round(base_w1, 4) if ok else None,
                  "label_dist": dict(sorted(cnt.items())), "pred_dist": dict(sorted(pred.items())),
                  "confusion_expected>pred": dict(sorted(conf.items())),
                  "spearman_valence_vs_score": round(rho, 4) if rho is not None else None,
                  "never_predicted_levels": [i for i in range(k) if pred[i] == 0]})
        res["k%d" % k] = s
        P(row("k=%d 完全命中" % k, s, "±1級內=%s MAE=%s級(正規化%s) 多數類基線: 命中%s ±1內%s 分布=%s" % (
            fmt(s["within1"], True), s["mae_levels"], s["mae_normalized"], fmt(s["baseline_majority_exact"], True),
            fmt(s["baseline_majority_within1"], True), s["label_dist"])))
        P("      預測分布=%s 從未被選的等級=%s Spearman(人工 Valence, score 欄位加權平均)=%s" % (
            s["pred_dist"], s["never_predicted_levels"], s["spearman_valence_vs_score"]))
    OUT["exp4"] = res


if __name__ == "__main__":
    exp1()
    exp2()
    exp3()
    if os.path.exists(os.path.join(DATA, "exp4_score_k3.jsonl")):
        exp4()
    json.dump(OUT, open(os.path.join(RESULTS, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(RESULTS, "tables.txt"), "w", encoding="utf-8").write("\n".join(T) + "\n")
    print("\n".join(T))
