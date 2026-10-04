"""極限測試員 A 共用工具：呼叫 jev CLI、計算指標。只用 Python 標準庫。"""
import json
import math
import os
import subprocess
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("JEV_DATA_DIR", os.path.join(BASE, "data", "massive"))
RESULTS = os.environ.get("JEV_RESULTS_DIR", os.path.join(BASE, "local-results", "A"))
os.makedirs(RESULTS, exist_ok=True)
JEV = os.environ.get("JEV_CLI", os.path.join(BASE, "jev-cli", "jev"))

# MASSIVE 官方 60 個 intent（取自 AmazonScience/massive 的 massive.py 的 _INTENTS 清單）
INTENTS = sorted(json.load(open(os.path.join(DATA, "massive_labels_zh_desc.json"), encoding="utf-8"))["intents"].keys())


def load_desc():
    return json.load(open(os.path.join(DATA, "massive_labels_zh_desc.json"), encoding="utf-8"))


FIXED_ENDPOINT = {"JEV_ENDPOINTS": os.environ.get("JEV_ENDPOINTS") or os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")}


def call(req, timeout=300, env_extra=None, retries=0, retry_wait=15):
    """用 `jev ask -` 送一個完整 request；回傳 exit code、牆鐘毫秒、解析後的 JSON。
    env_extra：額外環境變數（例如只用 gpu 量延遲）。retries：exit 1（無可用 endpoint）時重試次數。"""
    body = json.dumps(req, ensure_ascii=False).encode("utf-8")
    env = dict(os.environ, **(env_extra or {}))
    attempt = 0
    while True:
        t0 = time.perf_counter()
        p = subprocess.run([JEV, "ask", "-"], input=body, capture_output=True, timeout=timeout, env=env)
        ms = (time.perf_counter() - t0) * 1000
        out = p.stdout.decode("utf-8", "replace")
        try:
            data = json.loads(out)
        except ValueError:
            data = {"_raw": out[:2000]}
        if p.returncode == 1 and attempt < retries:
            attempt += 1
            time.sleep(retry_wait)
            continue
        return {"exit": p.returncode, "ms": round(ms, 1), "data": data, "retries": attempt,
                "stderr": p.stderr.decode("utf-8", "replace")[:500]}


def maxprob(ans):
    if ans.get("type") == "noul":
        p = float(ans.get("noul", 0.5))
        return max(p, 1 - p)
    probs = ans.get("probabilities") or {}
    return max(probs.values()) if probs else 0.0


def ece(pairs, bins=10):
    """與 jev eval 相同定義：信心＝最高機率（noul 取 max(p,1-p)），10 等寬 bin。"""
    if not pairs:
        return None
    total = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(c, ok) for c, ok in pairs if (lo < c <= hi) or (b == 0 and c == 0)]
        if sel:
            conf = sum(c for c, _ in sel) / len(sel)
            acc = sum(1 for _, ok in sel if ok) / len(sel)
            total += len(sel) / len(pairs) * abs(conf - acc)
    return round(total, 4)


def percentile(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    f, c = math.floor(k), math.ceil(k)
    return xs[int(k)] if f == c else xs[f] + (xs[c] - xs[f]) * (k - f)


def wilson(k, n, z=1.96):
    """二項比例的 Wilson 95% 信賴區間。"""
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def summarize(pairs, lat=None):
    """pairs: [(confidence, ok)]。回傳準確度、ECE、高信心錯誤率（兩種分母）、延遲。"""
    n = len(pairs)
    if not n:
        return {"n": 0}
    correct = sum(1 for _, ok in pairs if ok)
    hi = [(c, ok) for c, ok in pairs if c >= 0.9]
    hi_wrong = sum(1 for _, ok in hi if not ok)
    s = {"n": n, "correct": correct, "accuracy": round(correct / n, 4), "acc_ci95": wilson(correct, n), "ece": ece(pairs),
         "hiconf_wrong_of_all": round(hi_wrong / n, 4),
         "hiconf_n": len(hi),
         "hiconf_wrong_of_hiconf": round(hi_wrong / len(hi), 4) if hi else None,
         "mean_conf": round(sum(c for c, _ in pairs) / n, 4)}
    if lat:
        s["lat_ms_p50"] = round(percentile(lat, 0.5), 1)
        s["lat_ms_p95"] = round(percentile(lat, 0.95), 1)
    return s


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip() and not l.lstrip().startswith("//")]
