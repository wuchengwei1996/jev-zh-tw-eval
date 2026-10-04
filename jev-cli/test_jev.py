"""jev CLI 單元測試：全部打本機假伺服器，不連外網、不花錢。

跑法：python3 -m unittest discover -s <skill>/scripts -p 'test_*.py'
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import socket
import tempfile
import threading
import time
import unittest
import unittest.mock
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))


def load_jev():
    path = os.path.join(HERE, "jev")
    loader = importlib.machinery.SourceFileLoader("jev_cli", path)
    spec = importlib.util.spec_from_loader("jev_cli", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


jev = load_jev()


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class FakeServer:
    """可設定回應的假 Ollama／TypeSafe 伺服器，記錄收到的每個請求。"""

    def __init__(self, version_status=200, systemone=None, systemone_status=200, port=0,
                 redirect_to=None, tags=None, post_delay=0):
        self.requests = []
        self.redirect_to = redirect_to
        self.version_status = version_status
        self.systemone_status = systemone_status
        self.systemone = systemone or (lambda body: canned_answer(body))
        self.tags = tags if tags is not None else {"models": [{"name": "tev1:4b"}]}
        self.error_body = {"error": "fake error"}  # systemone_status≠200 時回的 body
        self.post_delay = post_delay          # >0：POST 掛住這麼多秒（模擬推論卡住）
        self.release = threading.Event()      # close() 時放掉掛住的 handler
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, status, obj):
                data = json.dumps(obj).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                outer.requests.append(("GET", self.path, dict(self.headers), None))
                if self.path == "/api/version":
                    self._send(outer.version_status, {"version": "0.35.0"})
                elif self.path == "/api/tags":
                    self._send(200, outer.tags)
                else:
                    self._send(404, {"error": "not found"})

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(n)
                body = json.loads(raw or b"{}")
                outer.requests.append(("POST", self.path, dict(self.headers), body, raw))
                if outer.post_delay:
                    if outer.release.wait(outer.post_delay):
                        return  # 測試結束：不回應，直接關
                if self.path == "/v1/systemone":
                    if outer.redirect_to:
                        self.send_response(302)
                        self.send_header("Location", outer.redirect_to)
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                    elif outer.systemone_status != 200:
                        self._send(outer.systemone_status, outer.error_body)
                    else:
                        self._send(200, outer.systemone(body))
                else:
                    self._send(404, {"error": "not found"})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def posts(self):
        return [r for r in self.requests if r[0] == "POST"]

    def tag_gets(self):
        return [r for r in self.requests if r[0] == "GET" and r[1] == "/api/tags"]

    def close(self):
        self.release.set()
        self.httpd.shutdown()
        self.httpd.server_close()


def canned_answer(body):
    answers = {}
    for qid, q in body.get("questions", {}).items():
        t = q["type"]
        if t == "noul":
            answers[qid] = {"type": "noul", "noul": 0.93}
        elif t == "choice":
            opts = list(q["criteria"].keys())
            p = {o: (0.8 if i == 0 else 0.2 / max(1, len(opts) - 1)) for i, o in enumerate(opts)}
            answers[qid] = {"type": "choice", "choice": opts[0], "probabilities": p, "confidence": 0.7}
        elif t == "score":
            n = len(q["criteria"])
            p = {str(i): (1.0 if i == n - 1 else 0.0) for i in range(n)}
            answers[qid] = {"type": "score", "score": float(n - 1),
                            "legend": {str(i): c for i, c in enumerate(q["criteria"])},
                            "probabilities": p, "confidence": 1.0}
    return {"model": body.get("model"), "answers": answers,
            "usage": {"input_tokens": 120, "output_tokens": 3}}


class JevTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = os.path.join(self.tmp.name, "cache")
        self.servers = []
        self.env_patch = {
            "JEV_CACHE_DIR": self.cache,
            "JEV_CONFIG": os.path.join(self.tmp.name, "missing-config.json"),
            "JEV_TYPESAFE_ENV_FILE": os.path.join(self.tmp.name, "no_typesafe_env"),
            "JEV_PROBE_TIMEOUT": "0.3",
        }
        for k in ("JEV_ENDPOINTS", "OLLAMA_URL", "JEV_MODEL", "JEV_BACKEND", "TYPESAFE_API_KEY",
                  "TYPESAFE_BASE_URL", "JEV_DAILY_INPUT_TOKEN_CAP", "JEV_POST_TIMEOUT",
                  "JEV_AUTOSTART_WAIT"):
            self.env_patch.setdefault(k, None)
        self._saved = {k: os.environ.get(k) for k in self.env_patch}
        for k, v in self.env_patch.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        # 記錄所有對外 URL，用來證明只連設定裡的位址
        self.urls = []
        self.timeouts = []  # (method, url, timeout)
        self._orig_open = jev._open
        test = self

        def recording_open(req, timeout=None):
            url = req.full_url if isinstance(req, urllib.request.Request) else req
            test.urls.append(url)
            method = req.get_method() if isinstance(req, urllib.request.Request) else "GET"
            test.timeouts.append((method, url, timeout))
            return test._orig_open(req, timeout)

        jev._open = recording_open

    def tearDown(self):
        jev._open = self._orig_open
        for s in self.servers:
            s.close()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def server(self, **kw):
        s = FakeServer(**kw)
        self.servers.append(s)
        return s

    def run_cli(self, *argv, stdin=None):
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = jev.main(list(argv), stdin=io.StringIO(stdin) if stdin is not None else None)
        text = out.getvalue()
        try:
            data = json.loads(text) if text.strip() else None
        except ValueError:
            data = None
        return code, data, text, err.getvalue()

    def set_endpoints(self, *pairs):
        os.environ["JEV_ENDPOINTS"] = ",".join("%s=%s" % p for p in pairs)


REQ = {
    "state": "I was charged twice. Please refund.",
    "questions": {
        "refund": {"type": "noul", "instructions": "Does the customer ask for money back?"},
        "team": {"type": "choice", "instructions": "Which team?",
                 "criteria": {"billing": None, "technical": None}},
        "urgency": {"type": "score", "instructions": "How urgent?",
                    "criteria": ["low", "medium", "high"]},
    },
}


class TestLocalBackend(JevTestCase):
    def test_passthrough_and_served_by(self):
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        os.environ["JEV_MODEL"] = "tev1:4b"
        code, data, text, err = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, err)
        sent = s.posts()[0][3]
        self.assertEqual(sent["state"], REQ["state"])
        self.assertEqual(sent["questions"], REQ["questions"])
        self.assertEqual(sent["model"], "tev1:4b")
        self.assertEqual(data["served_by"], "gpu")
        self.assertEqual(set(data["answers"]), {"refund", "team", "urgency"})
        self.assertAlmostEqual(sum(data["answers"]["team"]["probabilities"].values()), 1.0, places=6)

    def test_jev_model_name_maps_to_local_model(self):
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        os.environ["JEV_MODEL"] = "tev1:4b"
        req = dict(REQ, model="jev-latest")
        code, data, _, err = self.run_cli("ask", json.dumps(req))
        self.assertEqual(code, 0, err)
        self.assertEqual(s.posts()[0][3]["model"], "tev1:4b")

    def test_fallback_to_second_endpoint_and_cache(self):
        down = "http://127.0.0.1:%d" % free_port()
        s = self.server()
        self.set_endpoints(("gpu", down), ("mac", s.url))
        code, data, _, err = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, err)
        self.assertEqual(data["served_by"], "mac")
        probes_down = [u for u in self.urls if u.startswith(down)]
        self.assertEqual(len(probes_down), 1)
        # 第二次呼叫：快取記得 gpu 掛了，不再探測
        code, data, _, err = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, err)
        self.assertEqual(len([u for u in self.urls if u.startswith(down)]), 1)

    def test_unhealthy_version_endpoint_is_skipped(self):
        bad = self.server(version_status=503)
        good = self.server()
        self.set_endpoints(("bad", bad.url), ("good", good.url))
        code, data, _, err = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, err)
        self.assertEqual(data["served_by"], "good")
        self.assertEqual(bad.posts(), [])

    def test_model_missing_on_first_endpoint_falls_back(self):
        first = self.server(systemone_status=404)
        second = self.server()
        self.set_endpoints(("first", first.url), ("second", second.url))
        code, data, _, err = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, err)
        self.assertEqual(data["served_by"], "second")

    def test_bad_request_does_not_fall_back(self):
        first = self.server(systemone_status=400)
        second = self.server()
        self.set_endpoints(("first", first.url), ("second", second.url))
        code, data, _, err = self.run_cli("ask", json.dumps(REQ))
        self.assertNotEqual(code, 0)
        self.assertEqual(second.posts(), [])

    def test_all_endpoints_down_is_clear_error(self):
        self.set_endpoints(("a", "http://127.0.0.1:%d" % free_port()))
        code, data, text, err = self.run_cli("ask", json.dumps(REQ))
        self.assertNotEqual(code, 0)
        self.assertIn("endpoint", (text + err).lower())

    def test_only_configured_hosts_are_contacted(self):
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        self.run_cli("ask", json.dumps(REQ))
        self.assertTrue(self.urls)
        for u in self.urls:
            self.assertTrue(u.startswith(s.url), u)

    def test_too_many_options_rejected_locally_without_network(self):
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        crit = {"opt%d" % i: None for i in range(27)}
        req = {"state": "x", "questions": {"q": {"type": "choice", "instructions": "?", "criteria": crit}}}
        code, data, text, err = self.run_cli("ask", json.dumps(req))
        self.assertEqual(code, 2)
        self.assertIn("26", text + err)
        self.assertNotIn("typesafe", (text + err).lower())  # 條 6
        self.assertEqual(self.urls, [])

    def test_too_many_questions_rejected(self):
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        qs = {"q%d" % i: {"type": "noul", "instructions": "?"} for i in range(65)}
        code, *_ = self.run_cli("ask", json.dumps({"state": "x", "questions": qs}))
        self.assertEqual(code, 2)
        self.assertEqual(self.urls, [])

    def test_dry_run_makes_no_requests(self):
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        code, data, _, err = self.run_cli("--dry-run", "ask", json.dumps(REQ))
        self.assertEqual(code, 0, err)
        self.assertEqual(self.urls, [])
        self.assertTrue(data["dry_run"])
        self.assertEqual(data["request"]["questions"], REQ["questions"])

    def test_reads_request_from_stdin(self):
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        code, data, _, err = self.run_cli("ask", "-", stdin=json.dumps(REQ))
        self.assertEqual(code, 0, err)
        self.assertEqual(data["served_by"], "gpu")

    def test_usage_is_logged(self):
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        self.run_cli("ask", json.dumps(REQ))
        with open(os.path.join(self.cache, "usage.jsonl")) as f:
            rows = [json.loads(l) for l in f if l.strip()]
        self.assertEqual(rows[-1]["backend"], "local")
        self.assertEqual(rows[-1]["input_tokens"], 120)


class TestShortcuts(JevTestCase):
    def test_noul_shortcut(self):
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        code, data, _, err = self.run_cli("noul", "I want a refund", "Asks for money back?")
        self.assertEqual(code, 0, err)
        q = s.posts()[0][3]["questions"]
        self.assertEqual(list(q.values())[0], {"type": "noul", "instructions": "Asks for money back?"})

    def test_choice_shortcut(self):
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        code, data, _, err = self.run_cli("choice", "Login broken", "Which team?", "billing", "technical")
        self.assertEqual(code, 0, err)
        q = list(s.posts()[0][3]["questions"].values())[0]
        self.assertEqual(q["type"], "choice")
        self.assertEqual(q["criteria"], {"billing": None, "technical": None})

    def test_score_shortcut(self):
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        code, data, _, err = self.run_cli("score", "ANGRY!!!", "How angry?", "calm", "annoyed", "furious")
        self.assertEqual(code, 0, err)
        q = list(s.posts()[0][3]["questions"].values())[0]
        self.assertEqual(q["criteria"], ["calm", "annoyed", "furious"])


class TestTypesafeBackend(JevTestCase):
    def test_refuses_without_key_and_makes_no_requests(self):
        code, data, text, err = self.run_cli("--backend", "typesafe", "ask", json.dumps(REQ))
        self.assertEqual(code, 3)
        self.assertIn("TYPESAFE_API_KEY", text + err)
        self.assertEqual(self.urls, [])

    def _write_key(self, key="not-a-real-key"):
        path = os.environ["JEV_TYPESAFE_ENV_FILE"]
        with open(path, "w") as f:
            f.write("TYPESAFE_API_KEY=%s\n" % key)
        return key

    def test_uses_key_file_and_bearer_header(self):
        key = self._write_key()
        s = self.server()
        os.environ["TYPESAFE_BASE_URL"] = s.url
        code, data, _, err = self.run_cli("--backend", "typesafe", "ask", json.dumps(REQ))
        self.assertEqual(code, 0, err)
        post = s.posts()[0]
        self.assertEqual(post[2].get("Authorization"), "Bearer " + key)
        self.assertEqual(post[3]["model"], "jev-latest")
        self.assertEqual(data["served_by"], "typesafe")

    def test_daily_cap_blocks_before_sending(self):
        self._write_key()
        s = self.server()
        os.environ["TYPESAFE_BASE_URL"] = s.url
        os.environ["JEV_DAILY_INPUT_TOKEN_CAP"] = "1000"
        os.makedirs(self.cache, exist_ok=True)
        with open(os.path.join(self.cache, "usage.jsonl"), "w") as f:
            f.write(json.dumps({"ts": time.time(), "backend": "typesafe", "input_tokens": 990,
                                "output_tokens": 0}) + "\n")
        code, data, text, err = self.run_cli("--backend", "typesafe", "ask", json.dumps(REQ))
        self.assertEqual(code, 4)
        self.assertEqual(s.posts(), [])

    def test_local_usage_does_not_count_toward_cap(self):
        self._write_key()
        s = self.server()
        os.environ["TYPESAFE_BASE_URL"] = s.url
        os.environ["JEV_DAILY_INPUT_TOKEN_CAP"] = "1000"
        os.makedirs(self.cache, exist_ok=True)
        with open(os.path.join(self.cache, "usage.jsonl"), "w") as f:
            f.write(json.dumps({"ts": time.time(), "backend": "local", "input_tokens": 999999}) + "\n")
        code, *_ = self.run_cli("--backend", "typesafe", "ask", json.dumps(REQ))
        self.assertEqual(code, 0)


class TestEval(JevTestCase):
    def test_eval_reports_accuracy(self):
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        path = os.path.join(self.tmp.name, "set.jsonl")
        items = [
            {"id": "n1", "type": "noul", "state": "refund please", "instructions": "money back?",
             "expected": True},
            {"id": "n2", "type": "noul", "state": "thanks", "instructions": "money back?",
             "expected": False},
            {"id": "c1", "type": "choice", "state": "card charged twice", "instructions": "team?",
             "criteria": {"billing": None, "technical": None}, "expected": "billing"},
            {"id": "s1", "type": "score", "state": "FURIOUS", "instructions": "anger?",
             "criteria": ["calm", "annoyed", "furious"], "expected": 2},
        ]
        with open(path, "w") as f:
            for it in items:
                f.write(json.dumps(it) + "\n")
        code, data, _, err = self.run_cli("eval", path)
        self.assertEqual(code, 0, err)
        self.assertEqual(data["n"], 4)
        self.assertEqual(data["correct"], 3)  # 假伺服器 noul 永遠回 0.93，所以 n2 錯
        self.assertEqual([m["id"] for m in data["misses"]], ["n2"])
        self.assertEqual(data["misses"][0]["expected"], False)
        self.assertIn("ece", data)
        self.assertIn("latency_ms_p50", data)


# ── 以下為審查修正新增的測試（條號對應任務單） ─────────────────────────

class PopenCounter:
    def __init__(self, on_call=None):
        self.calls = []
        self.on_call = on_call

    def __call__(self, *a, **kw):
        self.calls.append(a)
        if self.on_call:
            self.on_call()
        return object()


class TestAutostart(JevTestCase):
    def _cfg(self, url):
        path = os.path.join(self.tmp.name, "cfg.json")
        with open(path, "w") as f:
            json.dump({"endpoints": [{"name": "l", "url": url, "autostart": True}]}, f)
        os.environ["JEV_CONFIG"] = path

    def _patch(self, on_call=None):
        popen = PopenCounter(on_call)
        for p in (unittest.mock.patch.object(jev.shutil, "which", lambda n: "/fake/ollama"),
                  unittest.mock.patch.object(jev.subprocess, "Popen", popen)):
            p.start()
            self.addCleanup(p.stop)
        os.environ["JEV_AUTOSTART_WAIT"] = "0.3"
        self.addCleanup(os.environ.pop, "JEV_AUTOSTART_WAIT", None)
        return popen

    def test_post_404_with_healthy_probe_never_autostarts(self):  # 條 1
        s = self.server(systemone_status=404)
        self._cfg(s.url)
        popen = self._patch()
        code, data, text, err = self.run_cli("ask", json.dumps(REQ))
        self.assertNotEqual(code, 0)
        self.assertLessEqual(len(popen.calls), 1)
        self.assertEqual(len(popen.calls), 0)
        self.assertIn("error", data)

    def test_post_5xx_with_healthy_probe_never_autostarts(self):  # 條 1
        s = self.server(systemone_status=503)
        self._cfg(s.url)
        popen = self._patch()
        code, data, text, err = self.run_cli("ask", json.dumps(REQ))
        self.assertNotEqual(code, 0)
        self.assertEqual(len(popen.calls), 0)
        self.assertIn("error", data)

    def test_autostart_failure_spawns_once_and_is_cached(self):  # 條 1
        self._cfg("http://127.0.0.1:%d" % free_port())
        popen = self._patch()
        code, data, _, _ = self.run_cli("ask", json.dumps(REQ))
        self.assertNotEqual(code, 0)
        self.assertIn("error", data)
        self.assertEqual(len(popen.calls), 1)
        code, data, _, _ = self.run_cli("ask", json.dumps(REQ))
        self.assertNotEqual(code, 0)
        self.assertEqual(len(popen.calls), 1)  # 60 秒內不再 spawn

    def test_autostart_success_posts_to_same_endpoint(self):  # 條 1
        port = free_port()
        self._cfg("http://127.0.0.1:%d" % port)
        started = []

        def spawn():
            srv = FakeServer(port=port)
            self.servers.append(srv)
            started.append(srv)

        popen = self._patch(spawn)
        code, data, _, err = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, err)
        self.assertEqual(len(popen.calls), 1)
        self.assertEqual(len(started[0].posts()), 1)
        self.assertEqual(data["served_by"], "l")


class TestTypesafeAccounting(JevTestCase):
    def setUp(self):
        super().setUp()
        with open(os.environ["JEV_TYPESAFE_ENV_FILE"], "w") as f:
            f.write("TYPESAFE_API_KEY=not-a-real-key\n")

    def ts(self, **kw):
        s = self.server(**kw)
        os.environ["TYPESAFE_BASE_URL"] = s.url
        return s

    def ask(self):
        return self.run_cli("--backend", "typesafe", "ask", json.dumps(REQ))

    def rows(self):
        with open(os.path.join(self.cache, "usage.jsonl")) as f:
            return [json.loads(l) for l in f if l.strip()]

    def test_cap_zero_refuses(self):  # 條 2
        s = self.ts()
        os.environ["JEV_DAILY_INPUT_TOKEN_CAP"] = "0"
        code, data, text, _ = self.ask()
        self.assertEqual(code, 4)
        self.assertIn("0", data["error"])
        self.assertEqual(s.posts(), [])

    def test_cap_negative_refuses(self):  # 條 2
        s = self.ts()
        os.environ["JEV_DAILY_INPUT_TOKEN_CAP"] = "-5"
        code, *_ = self.ask()
        self.assertEqual(code, 4)
        self.assertEqual(s.posts(), [])

    def test_server_500_keeps_estimate(self):  # 條 3
        self.ts(systemone_status=500)
        code, *_ = self.ask()
        self.assertNotEqual(code, 0)
        self.assertGreaterEqual(jev.today_tokens("typesafe"), jev.estimate_tokens(REQ))
        self.assertEqual([r["kind"] for r in self.rows()], ["reserve"])

    def test_missing_usage_keeps_estimate(self):  # 條 3
        self.ts(systemone=lambda b: {"model": "m", "answers": canned_answer(b)["answers"]})
        code, *_ = self.ask()
        self.assertEqual(code, 0)
        self.assertEqual(jev.today_tokens("typesafe"), jev.estimate_tokens(REQ))

    def test_success_settles_to_actual_usage(self):  # 條 3
        self.ts()
        code, *_ = self.ask()
        self.assertEqual(code, 0)
        self.assertEqual(jev.today_tokens("typesafe"), 120)
        rows = self.rows()
        self.assertEqual([r["kind"] for r in rows], ["reserve", "settle"])
        self.assertEqual(rows[0]["rid"], rows[1]["rid"])
        self.assertEqual(rows[0]["input_tokens"], jev.estimate_tokens(REQ))

    def test_legacy_rows_without_rid_still_count(self):  # 條 3
        os.makedirs(self.cache, exist_ok=True)
        with open(os.path.join(self.cache, "usage.jsonl"), "w") as f:
            f.write(json.dumps({"ts": time.time(), "backend": "typesafe", "input_tokens": 77}) + "\n")
        self.assertEqual(jev.today_tokens("typesafe"), 77)

    def test_concurrent_requests_cannot_bypass_cap(self):  # 條 3
        s = self.ts(systemone=lambda b: (time.sleep(0.6), canned_answer(b))[1])
        need = jev.estimate_tokens(REQ)
        os.environ["JEV_DAILY_INPUT_TOKEN_CAP"] = str(int(need * 1.5))
        cfg = jev.load_config()
        results = []

        def worker():
            try:
                jev.ask_typesafe(REQ, cfg)
                results.append("ok")
            except jev.JevError as e:
                results.append(e.code)

        ths = [threading.Thread(target=worker) for _ in range(4)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        self.assertEqual(results.count("ok"), 1, results)
        self.assertEqual(results.count(4), 3, results)
        self.assertEqual(len(s.posts()), 1)

    def test_local_backend_logs_single_row_no_lock(self):  # 條 3
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(len(self.rows()), 1)
        self.assertFalse(os.path.exists(os.path.join(self.cache, "usage.lock")))

    def test_400_422_exit_2(self):  # 條 11
        for status in (400, 422):
            s = self.ts(systemone_status=status)
            code, *_ = self.ask()
            self.assertEqual(code, 2, status)

    def test_redirect_is_not_followed(self):  # 條 8
        other = self.server()
        s = self.ts(redirect_to=other.url + "/v1/systemone")
        code, data, _, _ = self.ask()
        self.assertNotEqual(code, 0)
        self.assertEqual(other.requests, [])
        self.assertEqual(len(s.posts()), 1)

    def test_usage_unwritable_refuses_typesafe(self):  # 條 12
        s = self.ts()
        os.makedirs(os.path.join(self.cache, "usage.jsonl"))  # 目錄擋住 append
        code, data, _, _ = self.ask()
        self.assertEqual(code, 4)
        self.assertEqual(s.posts(), [])


class TestEstimate(unittest.TestCase):
    def test_conservative_estimate(self):  # 條 4
        q = {"q": {"type": "noul", "instructions": "x"}}
        qlen = len(json.dumps(q, ensure_ascii=False))
        est = jev.estimate_tokens({"state": "\u4e2d" * 100, "questions": q})
        self.assertEqual(est, 101 + (qlen + 2) // 3 + 50)
        ascii_est = jev.estimate_tokens({"state": "a" * 300, "questions": q})
        self.assertEqual(ascii_est, 101 + (qlen + 2) // 3 + 50)

    def test_state_multiplied_and_overhead_per_question(self):  # 條 4
        qs = {"a": {"type": "noul", "instructions": "x"}, "b": {"type": "noul", "instructions": "x"}}
        qlen = len(json.dumps(qs, ensure_ascii=False))
        est = jev.estimate_tokens({"state": "\u4e2d" * 100, "questions": qs})
        self.assertEqual(est, 101 * 2 + (qlen + 2) // 3 + 100)


class TestEnvAndMessages(JevTestCase):
    def test_jev_backend_env_is_ignored(self):  # 條 5
        s = self.server()
        ts = self.server()
        self.set_endpoints(("gpu", s.url))
        os.environ["TYPESAFE_BASE_URL"] = ts.url
        os.environ["JEV_BACKEND"] = "typesafe"
        code, data, _, err = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, err)
        self.assertEqual(data["served_by"], "gpu")
        self.assertEqual(ts.requests, [])


class TestHealthCache(JevTestCase):
    def test_concurrent_write_health_never_raises(self):  # 條 7
        errors = []

        def w(i):
            try:
                for j in range(20):
                    jev.write_health({"http://x/%d" % i: {"ok": True, "ts": time.time(), "n": j}})
            except Exception as e:  # noqa
                errors.append(e)

        ths = [threading.Thread(target=w, args=(i,)) for i in range(8)]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        self.assertEqual(errors, [])
        self.assertIsInstance(jev.read_health(), dict)

    def test_write_health_swallows_failures(self):  # 條 7
        with unittest.mock.patch.object(jev.tempfile, "mkstemp", side_effect=OSError("boom")):
            jev.write_health({"a": 1})  # 不得丟例外

    def test_404_model_missing_is_cached(self):  # 條 9
        first = self.server(systemone_status=404)
        second = self.server()
        self.set_endpoints(("first", first.url), ("second", second.url))
        for _ in range(2):
            code, data, _, err = self.run_cli("ask", json.dumps(REQ))
            self.assertEqual(code, 0, err)
            self.assertEqual(data["served_by"], "second")
        self.assertEqual(len(first.posts()), 1)

    def test_healthy_cache_expires_after_10s(self):  # 條 10
        dead = "http://127.0.0.1:%d" % free_port()
        os.makedirs(self.cache, exist_ok=True)
        with open(os.path.join(self.cache, "health.json"), "w") as f:
            json.dump({dead: {"ok": True, "ts": time.time() - 20}}, f)
        self.set_endpoints(("d", dead))
        self.run_cli("ask", json.dumps(REQ))
        self.assertTrue([u for u in self.urls if u.startswith(dead)])  # 有重新探測

    def test_unhealthy_cache_still_lasts_60s(self):  # 條 10
        dead = "http://127.0.0.1:%d" % free_port()
        os.makedirs(self.cache, exist_ok=True)
        with open(os.path.join(self.cache, "health.json"), "w") as f:
            json.dump({dead: {"ok": False, "ts": time.time() - 20}}, f)
        self.set_endpoints(("d", dead))
        self.run_cli("ask", json.dumps(REQ))
        self.assertEqual([u for u in self.urls if u.startswith(dead)], [])


class TestRobustness(JevTestCase):
    def test_non_dict_usage_rows_skipped(self):  # 條 11
        os.makedirs(self.cache, exist_ok=True)
        with open(os.path.join(self.cache, "usage.jsonl"), "w") as f:
            f.write("[1,2]\n3\n\"s\"\nnull\n")
            f.write(json.dumps({"ts": time.time(), "backend": "typesafe", "input_tokens": 5}) + "\n")
        self.assertEqual(jev.today_tokens("typesafe"), 5)

    def test_unknown_subcommand_is_json_exit_2(self):  # 條 11
        code, data, text, err = self.run_cli("bogus")
        self.assertEqual(code, 2)
        self.assertIn("error", data)

    def test_global_options_after_subcommand(self):  # 條 11
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        code, data, _, err = self.run_cli("noul", "st", "q?", "--model", "xmodel")
        self.assertEqual(code, 0, err)
        self.assertEqual(s.posts()[0][3]["model"], "xmodel")
        code, data, _, err = self.run_cli("noul", "st", "q?", "--dry-run")
        self.assertTrue(data["dry_run"])
        code, data, _, err = self.run_cli("--model", "ymodel", "noul", "st", "q?")
        self.assertEqual(s.posts()[-1][3]["model"], "ymodel")

    def test_redirect_not_followed_local(self):  # 條 8
        other = self.server()
        s = self.server(redirect_to=other.url + "/v1/systemone")
        self.set_endpoints(("r", s.url))
        code, *_ = self.run_cli("ask", json.dumps(REQ))
        self.assertNotEqual(code, 0)
        self.assertEqual(other.requests, [])

    def test_cache_dir_falls_back_to_tmp(self):  # 條 12
        blocker = os.path.join(self.tmp.name, "afile")
        with open(blocker, "w") as f:
            f.write("x")
        os.environ["JEV_CACHE_DIR"] = os.path.join(blocker, "sub")
        with unittest.mock.patch.object(jev.tempfile, "gettempdir", lambda: self.tmp.name):
            d = jev.cache_dir()
            self.assertEqual(d, os.path.join(self.tmp.name, "jev-%d" % os.getuid()))
            self.assertTrue(os.path.isdir(d))
            s = self.server()
            self.set_endpoints(("gpu", s.url))
            code, data, _, err = self.run_cli("ask", json.dumps(REQ))
            self.assertEqual(code, 0, err)

    def test_local_usage_write_failure_is_swallowed(self):  # 條 12
        os.makedirs(os.path.join(self.cache, "usage.jsonl"))
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        code, data, _, err = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, err)
        self.assertEqual(data["served_by"], "gpu")


# ── 以下為對抗驗證（2026-10-03）修正新增的測試；註解 A1–A7 對應任務單 A 段條號 ──

PIN = "368717f114a9"
GOOD_DIGEST = "368717f114a9fcaf125cded395977ae8f444b32badd150132e74e71002f76241"
BAD_DIGEST = "deadbeef0000aaaabbbbccccddddeeeeffff00001111222233334444555566667"


def plumb_tags(digest):
    return {"models": [{"name": "crh225/plumb-4b:latest", "model": "crh225/plumb-4b:latest",
                        "digest": digest}]}


def headers_lower(post):
    return {k.lower(): v for k, v in post[2].items()}


class TestUtf8Body(JevTestCase):
    def test_non_ascii_state_sent_as_raw_utf8(self):  # A1
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        state = "我要退款，商品有瑕疵。" * 100  # 1,100 個中文字
        code, data, _, err = self.run_cli("noul", state, "這則訊息是否要求退款？")
        self.assertEqual(code, 0, err)
        post = s.posts()[0]
        self.assertEqual(post[3]["state"], state)
        raw = post[4]
        self.assertFalse(b"\\u" in raw, "中文被跳脫成 \\uXXXX")
        self.assertIn("我要退款".encode("utf-8"), raw)
        # 每個中文字 3 bytes；若被跳脫成 \uXXXX 會是 6 bytes（> 6,600）
        self.assertLess(int(headers_lower(post)["content-length"]), 3 * 1100 + 400)


class TestBodySizeLimit(JevTestCase):
    def test_encode_body_boundary(self):  # A2
        base = len(json.dumps({"state": ""}, ensure_ascii=False).encode("utf-8"))
        ok = jev.encode_body({"state": "a" * (65536 - base)})
        self.assertEqual(len(ok), 65536)
        with self.assertRaises(jev.JevError) as cm:
            jev.encode_body({"state": "a" * (65537 - base)})
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("請求太大（65537 bytes，上限 65536）；請縮短 state 或分批", str(cm.exception))

    def test_oversize_local_request_exit_2_without_network(self):  # A2
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        code, data, text, err = self.run_cli("noul", "中" * 22000, "是否要求退款？")  # 66,000 bytes
        self.assertEqual(code, 2, text)
        self.assertIn("請求太大", data["error"])
        self.assertIn("上限 65536", data["error"])
        self.assertNotIn("沒有可用的 endpoint", text)
        self.assertEqual(self.urls, [])
        self.assertEqual(s.requests, [])

    def test_chinese_under_limit_is_sent(self):  # A1＋A2：21,000 字中文 UTF-8 約 63 KB，可以送
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        code, data, text, err = self.run_cli("noul", "中" * 21000, "是否要求退款？")
        self.assertEqual(code, 0, text)
        self.assertEqual(len(s.posts()), 1)

    def test_dry_run_reports_body_bytes_and_rejects_oversize(self):  # A2
        self.set_endpoints(("gpu", "http://127.0.0.1:%d" % free_port()))
        code, data, text, _ = self.run_cli("--dry-run", "noul", "中" * 10, "q?")
        self.assertEqual(code, 0, text)
        self.assertGreater(data["body_bytes"], 30)
        code, data, text, _ = self.run_cli("--dry-run", "noul", "中" * 22000, "q?")
        self.assertEqual(code, 2, text)
        self.assertIn("請求太大", data["error"])
        self.assertEqual(self.urls, [])

    def test_oversize_typesafe_refused_before_reserve(self):  # A2
        with open(os.environ["JEV_TYPESAFE_ENV_FILE"], "w") as f:
            f.write("TYPESAFE_API_KEY=not-a-real-key\n")
        s = self.server()
        os.environ["TYPESAFE_BASE_URL"] = s.url
        code, data, text, _ = self.run_cli("--backend", "typesafe", "noul", "a" * 70000, "q?")
        self.assertEqual(code, 2, text)
        self.assertIn("請求太大", data["error"])
        self.assertEqual(s.requests, [])
        self.assertFalse(os.path.exists(os.path.join(self.cache, "usage.jsonl")))


class TestClientErrors(JevTestCase):
    def _cfg(self, endpoints):
        path = os.path.join(self.tmp.name, "cfg.json")
        with open(path, "w") as f:
            json.dump({"endpoints": endpoints}, f)
        os.environ["JEV_CONFIG"] = path

    def test_4xx_except_404_is_request_error(self):  # A3
        for status in (400, 413, 422):
            first = self.server(systemone_status=status)
            second = self.server()
            dead = "http://127.0.0.1:%d" % free_port()
            self._cfg([{"name": "first", "url": first.url},
                       {"name": "dead", "url": dead, "autostart": True}])
            popen = PopenCounter()
            with unittest.mock.patch.object(jev.shutil, "which", lambda n: "/fake/ollama"), \
                    unittest.mock.patch.object(jev.subprocess, "Popen", popen):
                os.environ["JEV_AUTOSTART_WAIT"] = "0.3"
                code, data, text, _ = self.run_cli("ask", json.dumps(REQ))
            self.assertEqual(code, 2, (status, text))
            self.assertEqual(data["detail"], {"error": "fake error"}, status)
            self.assertIn(str(status), data["error"])
            self.assertEqual(popen.calls, [], status)          # 不觸發 autostart
            self.assertEqual(second.posts(), [], status)
            rec = jev.read_health().get(first.url) or {}
            self.assertNotEqual(rec.get("ok"), False, status)  # 不把主機標成故障
            self.assertFalse(rec.get("missing_models"), status)

    def test_token_limit_400_says_request_too_large(self):  # A2＋A3（實測：中文 11,043 字＝8,527 tokens）
        detail = {"error": "prompt 0 has 8527 tokens; expected 1–8192 (input is never truncated)"}
        s = self.server(systemone_status=400)
        s.error_body = detail
        self.set_endpoints(("gpu", s.url))
        code, data, text, _ = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 2, text)
        self.assertIn("請求太大", data["error"])
        self.assertIn("8527", data["error"])
        self.assertIn("8192", data["error"])
        self.assertEqual(data["detail"], detail)

    def test_408_marks_host_down_and_falls_back(self):  # 驗收第 4 點：408 是暫時性錯誤
        first = self.server(systemone_status=408)
        second = self.server()
        self.set_endpoints(("first", first.url), ("second", second.url))
        code, data, text, _ = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, text)
        self.assertEqual(data["served_by"], "second")
        self.assertIs(jev.read_health()[first.url]["ok"], False)
        code, data, text, _ = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(data["served_by"], "second")
        self.assertEqual(len(first.posts()), 1)  # 60 秒內不再打

    def test_429_skips_host_this_time_only(self):  # 驗收第 4 點：429 只跳過這一次
        first = self.server(systemone_status=429)
        second = self.server()
        self.set_endpoints(("first", first.url), ("second", second.url))
        code, data, text, _ = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, text)
        self.assertEqual(data["served_by"], "second")
        self.assertNotEqual((jev.read_health().get(first.url) or {}).get("ok"), False)
        first.systemone_status = 200
        code, data, text, _ = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, text)
        self.assertEqual(data["served_by"], "first")  # 忙完就恢復使用

    def test_413_host_still_used_next_time(self):  # A3
        s = self.server(systemone_status=413)
        self.set_endpoints(("gpu", s.url))
        code, *_ = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 2)
        s.systemone_status = 200
        code, data, _, err = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, err)
        self.assertEqual(data["served_by"], "gpu")


class TestPostTimeout(JevTestCase):
    def _post_timeouts(self):
        return [t for m, u, t in self.timeouts if m == "POST"]

    def test_default_post_timeout_is_40s(self):  # A4
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        code, *_ = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0)
        self.assertEqual(self._post_timeouts(), [40.0])

    def test_post_timeout_env_override(self):  # A4
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        os.environ["JEV_POST_TIMEOUT"] = "7.5"
        code, *_ = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0)
        self.assertEqual(self._post_timeouts(), [7.5])

    def test_invalid_post_timeout_is_request_error(self):  # A4
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        for bad in ("abc", "0", "-3"):
            os.environ["JEV_POST_TIMEOUT"] = bad
            code, data, text, _ = self.run_cli("ask", json.dumps(REQ))
            self.assertEqual(code, 2, (bad, text))
            self.assertIn("JEV_POST_TIMEOUT", data["error"])
        self.assertEqual(s.posts(), [])

    def test_hung_endpoint_times_out_and_falls_back(self):  # A4
        hung = self.server(post_delay=30)
        good = self.server()
        self.set_endpoints(("hung", hung.url), ("good", good.url))
        os.environ["JEV_POST_TIMEOUT"] = "1"
        t0 = time.time()
        code, data, text, err = self.run_cli("ask", json.dumps(REQ))
        elapsed = time.time() - t0
        self.assertEqual(code, 0, text)
        self.assertEqual(data["served_by"], "good")
        self.assertLess(elapsed, 4.0)
        self.assertGreaterEqual(elapsed, 0.9)
        rec = jev.read_health()[hung.url]
        self.assertIs(rec["ok"], False)
        # 60 秒內第二次呼叫不再打掛住的主機
        code, data, _, _ = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(data["served_by"], "good")
        self.assertEqual(len(hung.posts()), 1)


class TestModelDigest(JevTestCase):
    def _cfg(self, servers, digest=PIN, model="crh225/plumb-4b"):
        cfg = {"model": model, "endpoints": [{"name": n, "url": s.url} for n, s in servers]}
        if digest is not None:
            cfg["model_digest"] = digest
        path = os.path.join(self.tmp.name, "cfg.json")
        with open(path, "w") as f:
            json.dump(cfg, f)
        os.environ["JEV_CONFIG"] = path

    def test_mismatched_digest_endpoint_is_skipped(self):  # A5
        bad = self.server(tags=plumb_tags(BAD_DIGEST))
        good = self.server(tags=plumb_tags(GOOD_DIGEST))
        self._cfg([("bad", bad), ("good", good)])
        code, data, text, err = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, text)
        self.assertEqual(data["served_by"], "good")
        self.assertEqual(bad.posts(), [])

    def test_all_mismatched_error_names_pin(self):  # A5
        bad = self.server(tags=plumb_tags(BAD_DIGEST))
        self._cfg([("bad", bad)])
        code, data, text, err = self.run_cli("ask", json.dumps(REQ))
        self.assertNotEqual(code, 0)
        self.assertIn("模型版本與釘選的 368717f114a9 不符", data["error"])
        self.assertEqual(bad.posts(), [])

    def test_digest_checked_once_then_cached(self):  # A5
        good = self.server(tags=plumb_tags(GOOD_DIGEST))
        self._cfg([("good", good)])
        for _ in range(3):
            code, data, text, _ = self.run_cli("ask", json.dumps(REQ))
            self.assertEqual(code, 0, text)
        self.assertEqual(len(good.tag_gets()), 1)
        self.assertEqual(len(good.posts()), 3)

    def test_mismatch_result_is_cached(self):  # A5
        bad = self.server(tags=plumb_tags(BAD_DIGEST))
        good = self.server(tags=plumb_tags(GOOD_DIGEST))
        self._cfg([("bad", bad), ("good", good)])
        for _ in range(2):
            code, data, text, _ = self.run_cli("ask", json.dumps(REQ))
            self.assertEqual(data["served_by"], "good")
        self.assertEqual(len(bad.tag_gets()), 1)

    def test_pinned_model_not_listed_is_unusable(self):  # 驗收第 3 點
        empty = self.server(tags={"models": []})
        good = self.server(tags=plumb_tags(GOOD_DIGEST))
        self._cfg([("empty", empty), ("good", good)])
        code, data, text, _ = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, text)
        self.assertEqual(data["served_by"], "good")
        self.assertEqual(empty.posts(), [])
        self._cfg([("empty", empty)])
        code, data, text, _ = self.run_cli("ask", json.dumps(REQ))
        self.assertNotEqual(code, 0)
        self.assertIn("empty", data["error"])
        self.assertIn("crh225/plumb-4b", data["error"])
        self.assertEqual(empty.posts(), [])

    def test_digest_field_absent_is_not_checked(self):  # A5
        s = self.server(tags={"models": [{"name": "crh225/plumb-4b:latest"}]})
        self._cfg([("gpu", s)])
        code, data, text, _ = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, text)
        self.assertEqual(data["served_by"], "gpu")

    def test_no_pin_means_no_tags_request(self):  # A5
        s = self.server(tags=plumb_tags(BAD_DIGEST))
        self._cfg([("gpu", s)], digest=None)
        code, data, text, _ = self.run_cli("ask", json.dumps(REQ))
        self.assertEqual(code, 0, text)
        self.assertEqual(s.tag_gets(), [])

    def test_pin_not_applied_to_overridden_model(self):  # A5
        s = self.server(tags=plumb_tags(BAD_DIGEST))
        self._cfg([("gpu", s)])
        code, data, text, _ = self.run_cli("--model", "tev1:4b", "ask", json.dumps(REQ))
        self.assertEqual(code, 0, text)
        self.assertEqual(data["served_by"], "gpu")

    def test_digest_checked_after_autostart(self):  # A5
        port = free_port()
        path = os.path.join(self.tmp.name, "cfg.json")
        with open(path, "w") as f:
            json.dump({"model": "crh225/plumb-4b", "model_digest": PIN,
                       "endpoints": [{"name": "l", "url": "http://127.0.0.1:%d" % port,
                                      "autostart": True}]}, f)
        os.environ["JEV_CONFIG"] = path
        started = []

        def spawn():
            srv = FakeServer(port=port, tags=plumb_tags(BAD_DIGEST))
            self.servers.append(srv)
            started.append(srv)

        os.environ["JEV_AUTOSTART_WAIT"] = "2"
        with unittest.mock.patch.object(jev.shutil, "which", lambda n: "/fake/ollama"), \
                unittest.mock.patch.object(jev.subprocess, "Popen", PopenCounter(spawn)):
            code, data, text, _ = self.run_cli("ask", json.dumps(REQ))
        self.assertNotEqual(code, 0)
        self.assertIn("368717f114a9", data["error"])
        self.assertEqual(started[0].posts(), [])

    def test_doctor_shows_digest_and_match(self):  # A5
        bad = self.server(tags=plumb_tags(BAD_DIGEST))
        good = self.server(tags=plumb_tags(GOOD_DIGEST))
        self._cfg([("bad", bad), ("good", good)])
        code, data, text, _ = self.run_cli("doctor")
        self.assertEqual(code, 0, text)
        self.assertEqual(data["model_digest"], PIN)
        rows = {r["name"]: r for r in data["endpoints"]}
        self.assertTrue(rows["good"]["digest"].startswith(PIN))
        self.assertIs(rows["good"]["digest_match"], True)
        self.assertTrue(rows["bad"]["digest"].startswith("deadbeef"))
        self.assertIs(rows["bad"]["digest_match"], False)


class TestAgentFacingMessages(JevTestCase):
    def test_no_endpoint_message_suggests_doctor_not_pull(self):  # A6
        self.set_endpoints(("a", "http://127.0.0.1:%d" % free_port()))
        code, data, text, err = self.run_cli("ask", json.dumps(REQ))
        self.assertNotEqual(code, 0)
        self.assertIn("沒有可用的 endpoint", data["error"])
        self.assertIn("jev doctor", data["error"])
        self.assertIn("用戶", data["error"])
        self.assertNotIn("ollama pull", (text + err).lower())


class TestChoiceDuplicates(JevTestCase):
    def test_duplicate_choice_options_rejected(self):  # A7
        s = self.server()
        self.set_endpoints(("gpu", s.url))
        code, data, text, err = self.run_cli("choice", "Login broken", "Which team?",
                                             "billing", "technical", "billing")
        self.assertEqual(code, 2, text)
        self.assertIn("重複", data["error"])
        self.assertIn("billing", data["error"])
        self.assertEqual(self.urls, [])


if __name__ == "__main__":
    unittest.main()
