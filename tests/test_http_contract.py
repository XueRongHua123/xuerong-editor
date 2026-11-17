# -*- coding: utf-8 -*-
"""雪绒的钢铁雄心编辑器 —— 真 HTTP 接口契约测试。

这个文件补的是 qa/regress_all.py 的洞：那一套是进程内函数调用（getattr 模块找函数），
一个路由都没走过 HTTP；而路由名和 Python 函数名并不一致（例如 /api/country_techs 没有
同名函数），所以只有真发请求才能证明「路由 + 参数解析 + 返回形状」这整条链是通的。

做法：
  · setUpClass 里用 tempfile 造一个最小 mod 夹具（不碰用户真实 mod 目录）；
  · 用子进程起 focus_editor.py（端口 8769，避开正在用的 8765），轮询等它就绪；
  · 所有用例只通过 urllib.request 访问 127.0.0.1:8769，断言落在文件字节/数据结构上；
  · 跑完杀掉进程，并把 cache/options.json 恢复成进来时的字节。

直接运行：
    python tests/test_http_contract.py
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.dirname(HERE)                      # work/
FOCUS_EDITOR = os.path.join(WORK_DIR, "focus_editor.py")
OPTIONS_PATH = os.path.join(WORK_DIR, "cache", "options.json")

HOST = "127.0.0.1"
PORT = 8769
BASE_URL = "http://%s:%d" % (HOST, PORT)

READY_TIMEOUT = 300.0        # 首次启动要解析 schema / 建图标缓存，60 秒以上很正常
REQUEST_TIMEOUT = 180.0

# 用例条数。加删用例时同步改这里；main() 用它判定「没被意外跳过」。
EXPECTED_CASES = 21

# 6 条前缀路由的注册顺序。`dispatch_get` 先查精确表，未命中再按 GET_PREFIXES
# 的注册顺序逐个 startswith，命中第一个就返回——顺序即优先级。
# 这 6 个前缀两两不重叠，所以 HTTP 层面测不出顺序差异，只能直接查表断言。
EXPECTED_PREFIX_ORDER = ["/index", "/help", "/api/data", "/icons/", "/web/", "/mascot/"]


# ---------------------------------------------------------------- HTTP 小工具

def _request(method, path, body=None, timeout=REQUEST_TIMEOUT):
    """发一个真 HTTP 请求，返回 (status, payload)。

    payload 是解析后的 JSON（解析失败时是 {"_raw": 文本}）。HTTPError 也当响应返回，
    因为契约测试要能看清 4xx/5xx 到底回了什么。
    """
    url = BASE_URL + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            raw = resp.read()
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read()
    text = raw.decode("utf-8", "replace")
    try:
        payload = json.loads(text)
    except Exception:
        payload = {"_raw": text}
    if isinstance(payload, dict):
        payload["_status"] = status
    return status, payload


def GET(path, **query):
    if query:
        path = path + ("&" if "?" in path else "?") + urllib.parse.urlencode(query)
    return _request("GET", path)


def POST(path, body=None):
    return _request("POST", path, body if body is not None else {})


# ------------------------------------------------------------ 文本/文件小工具

def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def _read_text(path):
    with open(path, "rb") as f:
        return f.read().decode("utf-8-sig")


def _write_text(path, text, bom=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    raw = text.encode("utf-8")
    if bom:
        raw = b"\xef\xbb\xbf" + raw
    with open(path, "wb") as f:
        f.write(raw)


def _span_from_brace(text, i):
    """从 text[i]（一个 '{'）开始配对，返回 (起, 止) 下标。"""
    depth = 0
    for j in range(i, len(text)):
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i, j + 1
    return None


def _block_span(text, key):
    """找 `key = {` 的块，返回 (起, 止) 下标；找不到返回 None。"""
    m = re.search(r"(?m)^[\t ]*%s\s*=\s*\{" % re.escape(key), text)
    if not m:
        return None
    return _span_from_brace(text, text.index("{", m.start()))


def _block_text(text, key):
    span = _block_span(text, key)
    if not span:
        return None
    return text[span[0]:span[1]]


def _focus_block(text, fid):
    """取某个国策节点的块。

    HOI4 里节点的键名统一是 `focus`，节点 id 写在块内的 `id = ...`，
    所以不能按 `TST_alpha_2 = {` 去找。
    """
    for m in re.finditer(r"(?m)^[\t ]*focus\s*=\s*\{", text):
        span = _span_from_brace(text, m.end() - 1)
        if not span:
            continue
        block = text[span[0]:span[1]]
        if re.search(r"(?m)^[\t ]*id\s*=\s*%s\s*$" % re.escape(fid), block):
            return block
    return None


# ------------------------------------------------------------------ mod 夹具

FOCUS_TREE_TEXT = """focus_tree = {
\tid = tree_alpha
\tcountry = {
\t\tfactor = 0
\t\tmodifier = {
\t\t\tadd = 10
\t\t\tTAG = TST
\t\t}
\t}
\tdefault = no
\tfocus = {
\t\tid = TST_alpha_1
\t\tx = 0
\t\ty = 0
\t\tcost = 1
\t\ticon = GFX_focus_generic
\t\tcompletion_reward = {
\t\t\tadd_political_power = 10
\t\t}
\t}
\tfocus = {
\t\tid = TST_alpha_2
\t\tprerequisite = { focus = TST_alpha_1 }
\t\tx = 2
\t\ty = 0
\t\tcost = 1
\t\ticon = GFX_focus_generic
\t\tcompletion_reward = {
\t\t\tadd_stability = 0.01
\t\t}
\t}
}

focus_tree = {
\tid = tree_beta
\tcountry = {
\t\tfactor = 0
\t\tmodifier = {
\t\t\tadd = 10
\t\t\tTAG = TST
\t\t}
\t}
\tdefault = no
\tfocus = {
\t\tid = TST_beta_1
\t\tx = 0
\t\ty = 0
\t\tcost = 1
\t\ticon = GFX_focus_generic
\t\tcompletion_reward = {
\t\t\tadd_war_support = 0.02
\t\t}
\t}
}
"""

STATE_TEXT = """state = {
\tid = 1
\tname = "STATE_TEST_1"
\tmanpower = 120000
\tstate_category = rural
\thistory = {
\t\towner = TST
\t\tadd_core_of = TST
\t}
\tprovinces = {
\t\t1 2 3
\t}
}
"""

COUNTRY_HIST_TEXT = """set_technology = {
\tinfantry_weapons = 1
}

complete_national_focus = {
\tfocus = TST_alpha_1
}
"""

EXTRA_TREE_TEXT = """focus_tree = {
\tid = tree_extra
\tcountry = {
\t\tfactor = 0
\t}
\tdefault = no
\tfocus = {
\t\tid = EXTRA_1
\t\tx = 0
\t\ty = 0
\t\tcost = 1
\t\ticon = GFX_focus_generic
\t}
}
"""

THIRD_TREE_TEXT = EXTRA_TREE_TEXT.replace("tree_extra", "tree_third").replace(
    "EXTRA_1", "THIRD_1")


def build_min_mod(root, tree_text=FOCUS_TREE_TEXT, tag="TST", tree_name="zz_bom_tree.txt",
                  bom=True):
    """造一个最小但能表达四个回归锚点的 mod 夹具。"""
    _write_text(os.path.join(root, "descriptor.mod"),
                'name="TST Test Mod"\nversion="0.1"\nsupported_version="1.5.*"\n'
                'tags={\n\t"Alternative History"\n}\nreplace_path="common/national_focus"\n')
    _write_text(os.path.join(root, "common", "country_tags", "zz_test.txt"),
                '%s = "countries/%s.txt"\n' % (tag, tag))
    _write_text(os.path.join(root, "common", "countries", "%s.txt" % tag),
                "color = { 120 140 160 }\ngraphical_culture = western_european_gfx\n")
    _write_text(os.path.join(root, "common", "national_focus", tree_name),
                tree_text, bom=bom)
    _write_text(os.path.join(root, "history", "states", "1-test.txt"), STATE_TEXT)
    _write_text(os.path.join(root, "history", "countries", "%s - Test.txt" % tag),
                COUNTRY_HIST_TEXT)
    return root


# --------------------------------------------------------------- 服务子进程

BOOT_TEMPLATE = (
    "import sys, types, runpy\n"
    "_stub = types.ModuleType('webbrowser')\n"
    "_stub.open = lambda *a, **k: False\n"
    "_stub.open_new = _stub.open\n"
    "_stub.open_new_tab = _stub.open\n"
    "sys.modules['webbrowser'] = _stub\n"
    "sys.argv = %r\n"
    "runpy.run_path(%r, run_name='__main__')\n"
)


class ServerProcess(object):
    """focus_editor.py 的子进程封装：起、等就绪、收输出、杀。"""

    def __init__(self, mod_dir, game_dir, port=PORT):
        self.argv = ["focus_editor.py", "--mod", mod_dir, "--game", game_dir,
                     "--port", str(port)]
        self.proc = None
        self.lines = []
        self._reader = None

    def _tail(self, n=60):
        return "\n".join(self.lines[-n:]) or "(无输出)"

    def start(self):
        boot = BOOT_TEMPLATE % (self.argv, FOCUS_EDITOR)
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        self.proc = subprocess.Popen(
            [sys.executable, "-X", "utf8", "-c", boot],
            cwd=WORK_DIR, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
        )
        self._reader = threading.Thread(target=self._pump, name="srv-out")
        self._reader.daemon = True
        self._reader.start()

    def _pump(self):
        try:
            for raw in iter(self.proc.stdout.readline, b""):
                self.lines.append(raw.decode("utf-8", "replace").rstrip())
        except Exception:
            pass

    def wait_ready(self, timeout=READY_TIMEOUT):
        deadline = time.time() + timeout
        last = ""
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(
                    "服务进程提前退出（exit=%s），最后输出：\n%s"
                    % (self.proc.returncode, self._tail()))
            try:
                status, _payload = _request("GET", "/api/playset", timeout=5.0)
                if status == 200:
                    return
                last = "HTTP %s" % status
            except Exception as e:                       # 还没监听
                last = "%s: %s" % (type(e).__name__, e)
            time.sleep(0.5)
        raise RuntimeError(
            "服务 %.0f 秒内没有就绪（最后一次：%s），输出尾部：\n%s"
            % (timeout, last, self._tail()))

    def stop(self):
        if not self.proc:
            return
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                try:
                    self.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
        try:
            if self.proc.stdout:
                self.proc.stdout.close()
        except Exception:
            pass
        self.proc = None


# ---------------------------------------------------------------- 用例本体

class HttpContractTest(unittest.TestCase):
    """20 条契约用例。顺序即 test_01..test_20，后面的用例依赖前面的写入结果。"""

    maxDiff = None

    # ---------------- 一次性环境 ----------------

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="xr_http_contract_")
        cls.mod = os.path.join(cls.tmpdir, "TST Test Mod")
        cls.game = os.path.join(cls.tmpdir, "game")          # 故意留空：只用夹具数据
        os.makedirs(cls.game)
        build_min_mod(cls.mod)

        cls._options_backup = None
        cls._had_options = os.path.exists(OPTIONS_PATH)
        if cls._had_options:
            cls._options_backup = _read_bytes(OPTIONS_PATH)
        # 不跟依赖、不拉启动器已启用列表，否则 dlc_load.json 里的真实 mod 会混进来
        os.makedirs(os.path.dirname(OPTIONS_PATH), exist_ok=True)
        _write_text(OPTIONS_PATH, '{"follow_deps": false, "follow_launcher": false}\n')

        cls.srv = ServerProcess(cls.mod, cls.game)
        try:
            cls.srv.start()
            cls.srv.wait_ready()
        except Exception:
            cls._restore_options()
            try:
                cls.srv.stop()
            finally:
                shutil.rmtree(cls.tmpdir, ignore_errors=True)
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            cls.srv.stop()
        finally:
            cls._restore_options()
            shutil.rmtree(cls.tmpdir, ignore_errors=True)

    @classmethod
    def _restore_options(cls):
        if cls._options_backup is not None:
            with open(OPTIONS_PATH, "wb") as f:
                f.write(cls._options_backup)
        elif not cls._had_options and os.path.exists(OPTIONS_PATH):
            os.remove(OPTIONS_PATH)

    # ---------------- 断言辅助 ----------------

    def api_get(self, path, **query):
        status, body = GET(path, **query)
        self.assertEqual(status, 200,
                         "GET %s 返回 HTTP %s：%s" % (path, status, body))
        return body

    def api_post(self, path, body):
        status, payload = POST(path, body)
        self.assertEqual(status, 200,
                         "POST %s 返回 HTTP %s（请求体 %s）：%s"
                         % (path, status, json.dumps(body, ensure_ascii=False), payload))
        return payload

    def post_ok(self, path, body):
        payload = self.api_post(path, body)
        self.assertIs(payload.get("ok"), True,
                      "POST %s 没成功：%s" % (path, json.dumps(payload, ensure_ascii=False)))
        return payload

    def mod_file(self, *parts):
        return os.path.join(self.mod, *parts)

    def assert_error_payload(self, payload, path):
        """错误路径的统一要求：200 + ok:false + 有 msg，不能 500、不能断连。"""
        self.assertEqual(payload.get("_status"), 200,
                         "%s 错误路径返回了 HTTP %s：%s"
                         % (path, payload.get("_status"),
                            json.dumps(payload, ensure_ascii=False)))
        self.assertIs(payload.get("ok"), False,
                      "%s 错误路径没有返回 ok:false：%s"
                      % (path, json.dumps(payload, ensure_ascii=False)))
        self.assertTrue((payload.get("msg") or "").strip(),
                        "%s 错误路径的 msg 是空的：%s"
                        % (path, json.dumps(payload, ensure_ascii=False)))

    # ---------------- 1. /api/data 的形状 ----------------

    def test_01_data_payload_shape(self):
        body = self.api_get("/api/data")
        self.assertIn("roots", body)
        self.assertIn("layers", body)
        self.assertIn("trees", body)

        # roots = 用户手动加的 mod（绝对路径），必须包含夹具
        paths = [os.path.normcase(r.get("path", "")) for r in body["roots"]]
        self.assertIn(os.path.normcase(self.mod), paths,
                      "roots 里没有夹具路径：%s" % paths)
        self.assertTrue(all("name" in r and "readonly" in r for r in body["roots"]))

        # layers = 真正读到的叠加链：首层是游戏本体，而且必须有一层指向夹具
        self.assertTrue(body["layers"], "layers 是空的")
        game_layers = [l for l in body["layers"] if l.get("game")]
        self.assertEqual(len(game_layers), 1, "layers 里游戏本体层不唯一：%s" % body["layers"])
        self.assertEqual(os.path.normcase(game_layers[0]["path"]),
                         os.path.normcase(self.game))
        manual = [l for l in body["layers"]
                  if os.path.normcase(l.get("path", "")) == os.path.normcase(self.mod)]
        self.assertEqual(len(manual), 1, "layers 里没有夹具层：%s" % body["layers"])
        self.assertFalse(manual[0].get("game"))
        self.assertIn(manual[0].get("reason"), ("manual", "dep", "launcher"))

        # trees 每一项都得是可用的结构，focuses 是节点数组而不是数量
        self.assertTrue(body["trees"], "trees 是空的")
        for t in body["trees"]:
            self.assertIsInstance(t.get("id"), str)
            self.assertIsInstance(t.get("file"), str)
            self.assertIsInstance(t.get("focuses"), list,
                                  "trees 里的 focuses 不是列表：%r" % (t.get("focuses"),))

        alpha = [t for t in body["trees"] if t["id"] == "tree_alpha"]
        self.assertEqual(len(alpha), 1, "trees 里没有 tree_alpha")
        self.assertEqual(len(alpha[0]["focuses"]), 2)
        ids = [f["id"] for f in alpha[0]["focuses"]]
        self.assertEqual(sorted(ids), ["TST_alpha_1", "TST_alpha_2"])

    # ---------------- 2. /api/states ----------------

    def test_02_states_list(self):
        body = self.api_get("/api/states")
        # 这个接口不带 ok 字段（其余写接口都带），只有 count/list —— 按真实形状断言
        self.assertEqual(body.get("count"), len(body["list"]))
        rows = {int(r["id"]): r for r in body["list"]}
        self.assertIn(1, rows, "states 里没有夹具州 1：%s" % list(rows))
        row = rows[1]
        self.assertEqual(row["owner"], "TST")
        self.assertEqual(row["name"], "STATE_TEST_1")
        self.assertEqual(row["raw_name"], "STATE_TEST_1")
        self.assertEqual(row["category"], "rural")
        self.assertEqual(str(row["manpower"]), "120000")
        self.assertIsInstance(row["buildings"], int)
        # 列表里的 cores/provinces 是数量（详情里才是明细），键名也不叫 province_count
        self.assertEqual(row["cores"], 1)
        self.assertEqual(row["provinces"], 3)
        self.assertTrue(row["file"].replace("\\", "/").endswith("history/states/1-test.txt"),
                        "states 的 file 不对：%s" % row["file"])

    # ---------------- 3. /api/state 详情 ----------------

    def test_03_state_detail(self):
        body = self.api_get("/api/state", id=1, full=1)
        self.assertIs(body.get("ok"), True, "state 详情失败：%s" % body)
        self.assertEqual(body["id"], 1)
        self.assertEqual(body["province_count"], 3)
        self.assertEqual(sorted(int(p) for p in body["provinces"]), [1, 2, 3])
        self.assertIsInstance(body["buildings"], dict)
        self.assertIsInstance(body["resources"], dict)
        self.assertEqual(body["owner"], "TST")
        self.assertIn("TST", body["cores"])
        self.assertEqual(body["category"], "rural")
        self.assertTrue(body["file"].replace("\\", "/").endswith("history/states/1-test.txt"),
                        "state 的 file 不对：%s" % body["file"])
        self.assertIs(body["writable"], True)
        # 夹具里没有任何建筑/资源，读出来必须是空表而不是报错
        self.assertEqual(body["buildings"], {})
        self.assertEqual(body["resources"], {})

    # ---------------- 4. /api/country_techs（POST） ----------------

    def test_04_country_techs(self):
        body = self.post_ok("/api/country_techs", {"root": self.mod, "tag": "TST"})
        self.assertEqual(body["tag"], "TST")
        self.assertIn("infantry_weapons", body["unlocked"],
                      "国家历史里的 set_technology 没被读出来：%s" % body["unlocked"])
        self.assertEqual(body["count"], len(body["unlocked"]))
        # 这个接口的 file 只给文件名，不是相对路径
        self.assertEqual(body["file"], "TST - Test.txt")
        # groups 是「按 folder 归组后的已知科技」，空 game 目录下没有科技定义
        self.assertEqual(body["total"], sum(len(g["techs"]) for g in body["groups"]))
        self.assertIn("1 项科技", body["msg"])

    # ---------------- 5. /api/focus_graph ----------------

    def test_05_focus_graph(self):
        body = self.api_get("/api/focus_graph", tree="tree_alpha")
        self.assertIs(body.get("ok"), True, "focus_graph 失败：%s" % body)
        self.assertEqual(body["tree"], "tree_alpha")
        self.assertEqual(body["count"], 2)
        nodes = {n["id"]: n for n in body["nodes"]}
        self.assertEqual(sorted(nodes), ["TST_alpha_1", "TST_alpha_2"])
        self.assertEqual(nodes["TST_alpha_1"]["x"], 0)
        self.assertEqual(nodes["TST_alpha_2"]["x"], 2)
        # 图上 cost 是字符串（原样来自文件），按数值比
        self.assertEqual(float(nodes["TST_alpha_2"]["cost"]), 1)
        self.assertEqual(nodes["TST_alpha_2"]["prereq"], [["TST_alpha_1"]])
        edges = [(e["from"], e["to"], e["kind"]) for e in body["edges"]]
        self.assertIn(("TST_alpha_1", "TST_alpha_2", "prereq"), edges,
                      "前置连线没解析出来：%s" % edges)
        self.assertEqual(body["file"], "zz_bom_tree.txt")

    # ---------------- 6. 保存节点 x/y/cost（字节断言） ----------------

    def test_06_save_focus_rewrites_bytes(self):
        path = self.mod_file("common", "national_focus", "zz_bom_tree.txt")
        before = _read_bytes(path)
        self.assertTrue(before.startswith(b"\xef\xbb\xbf"), "夹具国策文件应当带 BOM")

        body = self.post_ok("/api/save", {
            "root": self.mod,
            "file": "common/national_focus/zz_bom_tree.txt",
            "id": "TST_alpha_2",
            "fields": {"x": 4, "y": 3, "cost": 2},
        })
        self.assertEqual(body.get("msg"), "已保存")

        after = _read_bytes(path)
        self.assertNotEqual(before, after, "接口说保存了，但文件字节没变")
        self.assertTrue(after.startswith(b"\xef\xbb\xbf"),
                        "保存后 BOM 被吃掉了（HOI4 会因此把 BOM 当内容）")

        text = after.decode("utf-8-sig")
        block = _focus_block(text, "TST_alpha_2")
        self.assertTrue(block, "文件里找不到 TST_alpha_2 块：\n%s" % text)
        self.assertRegex(block, r"(?m)^[\t ]*x\s*=\s*4\s*$")
        self.assertRegex(block, r"(?m)^[\t ]*y\s*=\s*3\s*$")
        self.assertRegex(block, r"(?m)^[\t ]*cost\s*=\s*2\s*$")
        # 没动到的节点保持原样
        other = _focus_block(text, "TST_alpha_1")
        self.assertRegex(other, r"(?m)^[\t ]*x\s*=\s*0\s*$")
        self.assertIn("add_political_power = 10", other)

        # 结构侧同步：图上的坐标也得跟着变
        graph = self.api_get("/api/focus_graph", tree="tree_alpha")
        node = [n for n in graph["nodes"] if n["id"] == "TST_alpha_2"][0]
        self.assertEqual((node["x"], node["y"], float(node["cost"])), (4, 3, 2))

    # ---------------- 7. state_save：建筑进 history、资源在顶层 ----------------

    def test_07_state_save_buildings_and_resources(self):
        path = self.mod_file("history", "states", "1-test.txt")
        before = _read_bytes(path)

        body = self.post_ok("/api/state_save", {
            "id": 1,
            "fields": {
                "buildings": {"arms_factory": 2},
                "resources": {"steel": 5},
            },
        })
        self.assertTrue(body.get("diff"), "state_save 没返回 diff：%s" % body)
        self.assertNotEqual(_read_bytes(path), before, "接口说写入了，但州文件字节没变")

        text = _read_text(path)
        state_span = _block_span(text, "state")
        hist_span = _block_span(text, "history")
        res_span = _block_span(text, "resources")
        self.assertTrue(state_span and hist_span, "州文件结构没了：\n%s" % text)
        self.assertTrue(res_span, "state_save 没写 resources 块：\n%s" % text)

        history = text[hist_span[0]:hist_span[1]]
        # 建筑必须落在 history 块内部 —— 写在 state 顶层游戏读不到
        self.assertRegex(history, r"(?m)^[\t ]*arms_factory\s*=\s*2\s*$",
                         "arms_factory 没写进 history：\n%s" % history)
        # 资源必须在 state 顶层，而不是被塞进 history
        self.assertTrue(res_span[0] > hist_span[1],
                        "resources 块出现在 history 之前/内部：\n%s" % text)
        self.assertRegex(text[res_span[0]:res_span[1]],
                         r"(?m)^[\t ]*steel\s*=\s*5\s*$")
        self.assertNotIn("steel", history, "resources 被写进了 history 块")
        self.assertNotIn("arms_factory", text[state_span[0]:hist_span[0]],
                         "arms_factory 出现在 history 之前的顶层")
        self.assertNotIn("arms_factory", text[hist_span[1]:state_span[1]],
                         "arms_factory 出现在 history 之后的顶层")
        # 原有内容不能被写丢
        self.assertIn("owner = TST", history)
        self.assertIn("provinces = {", text)

        detail = self.api_get("/api/state", id=1)
        self.assertEqual(detail["buildings"], {"arms_factory": 2})
        self.assertEqual(detail["resources"], {"steel": 5})

    # ---------------- 8. decision_add（新类别注册文件不带 BOM） ----------------

    def test_08_decision_add_new_category(self):
        body = self.post_ok("/api/decision_add", {
            "root": self.mod,
            "id": "TST_test_decision",
            "category": "TST_test_category",
            "icon": "GFX_decision_generic_rocket",
            "cost": 50,
            "effect": "add_political_power = 25",
        })
        self.assertIn("TST_test_decision", json.dumps(body, ensure_ascii=False))

        cat_path = self.mod_file("common", "decisions", "categories",
                                 "zz_editor_categories.txt")
        self.assertTrue(os.path.exists(cat_path),
                        "新类别没写注册文件：%s" % cat_path)
        raw = _read_bytes(cat_path)
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"),
                         "类别注册文件带了 UTF-8 BOM —— HOI4 会把 BOM 吃进类别名")
        cat_text = raw.decode("utf-8")
        block = _block_text(cat_text, "TST_test_category")
        self.assertTrue(block, "注册文件里没有类别块：\n%s" % cat_text)
        self.assertIn("always = yes", block)

        dec_path = self.mod_file("common", "decisions", "zz_editor_decisions.txt")
        self.assertTrue(os.path.exists(dec_path), "决议文件没生成：%s" % dec_path)
        dec_text = _read_text(dec_path)
        dblock = _block_text(dec_text, "TST_test_decision")
        self.assertTrue(dblock, "决议文件里没有 TST_test_decision：\n%s" % dec_text)
        self.assertIn("TST_test_category", dec_text)

    # ---------------- 9. character_add ----------------

    def test_09_character_add(self):
        body = self.post_ok("/api/character_add", {
            "root": self.mod,
            "id": "TST_char_1",
            "name": "测试将领",
            "type": "corps_commander",
            "skill": 4,
            "attack": 3,
            "defense": 2,
            "planning": 1,
            "logistics": 5,
        })
        self.assertIn("TST_char_1", json.dumps(body, ensure_ascii=False))

        path = self.mod_file("common", "characters", "zz_editor_characters.txt")
        self.assertTrue(os.path.exists(path), "人物文件没生成：%s" % path)
        text = _read_text(path)
        block = _block_text(text, "TST_char_1")
        self.assertTrue(block, "人物文件里没有 TST_char_1：\n%s" % text)
        self.assertIn("corps_commander", block)
        self.assertIn("测试将领", block)
        self.assertRegex(block, r"(?m)^[\t ]*skill\s*=\s*4\s*$")

    # ---------------- 10. bookmark_add + /api/bookmarks ----------------

    def test_10_bookmark_add(self):
        name = "测试书签"
        body = self.post_ok("/api/bookmark_add", {
            "root": self.mod,
            "name": name,
            "date": "1937.1.1",
            "desc": "契约测试用",
            "default_country": "TST",
            "countries": ["TST"],
        })
        key = "ZZ_EDITOR_BM_" + hashlib.md5(name.encode("utf-8")).hexdigest()[:8].upper()
        # 返回值里的 msg 会回述补全后的日期，但不回述本地化 key
        self.assertIn("1937.1.1.12", body.get("msg", ""))
        self.assertIn("1 个国家", body.get("msg", ""))

        path = self.mod_file("common", "bookmarks", "zz_editor_bookmarks.txt")
        self.assertTrue(os.path.exists(path), "书签文件没生成：%s" % path)
        text = _read_text(path)
        block = _block_text(text, "bookmark")
        self.assertTrue(block, "书签文件里没有 bookmark 块：\n%s" % text)
        self.assertIn('name = "%s"' % key, block,
                      "书签的本地化 key 不对（应为 ZZ_EDITOR_BM_+md5 前 8 位）：\n%s" % block)
        self.assertIn("%s_DESC" % key, block)
        # 日期必须补成三段（1937.1.1 -> 1937.1.1.12）
        self.assertRegex(block, r"(?m)^[\t ]*date\s*=\s*1937\.1\.1\.12\s*$")
        self.assertIn('default_country = "TST"', block)

        listing = self.post_ok("/api/bookmarks", {"root": self.mod})
        self.assertEqual(listing["count"], len(listing["items"]))
        names = [i.get("name") for i in listing["items"]]
        self.assertIn(key, names, "bookmarks 列表里没有刚加的书签：%s" % names)
        # 列表里 countries 与 country_count 必须自洽（当前只认带引号的 tag 键，
        # 夹具写成裸键 TST = { ... }，所以这里是空表；不自洽才是 bug）
        item = [i for i in listing["items"] if i["name"] == key][0]
        self.assertEqual(item["country_count"], len(item["countries"]))

    # ---------------- 11. idea ----------------

    def test_11_idea_add(self):
        self.post_ok("/api/add_idea", {"root": self.mod, "id": "TST_idea_1"})
        path = self.mod_file("common", "ideas", "zz_focus_editor_ideas.txt")
        self.assertTrue(os.path.exists(path), "国家精神文件没生成：%s" % path)
        text = _read_text(path)
        self.assertIn("ideas = {", text)
        block = _block_text(text, "TST_idea_1")
        self.assertTrue(block, "国家精神文件里没有 TST_idea_1：\n%s" % text)

        # 重复 id 必须被挡（同一个文件里不该出现两份）
        dup = self.api_post("/api/add_idea", {"root": self.mod, "id": "TST_idea_1"})
        self.assertIs(dup.get("ok"), False, "重复 id 竟然成功了：%s" % dup)
        self.assertEqual(_read_text(path).count("TST_idea_1 = {"), 1)

    # ---------------- 12. tech ----------------

    def test_12_tech_add(self):
        self.post_ok("/api/tech_add", {
            "root": self.mod,
            "id": "TST_tech_1",
            "folder": "test_folder",
            "year": "1937",
        })
        path = self.mod_file("common", "technologies", "zz_focus_editor_technologies.txt")
        self.assertTrue(os.path.exists(path), "科技文件没生成：%s" % path)
        text = _read_text(path)
        self.assertIn("technologies = {", text)
        block = _block_text(text, "TST_tech_1")
        self.assertTrue(block, "科技文件里没有 TST_tech_1：\n%s" % text)
        self.assertRegex(block, r"(?m)^[\t ]*start_year\s*=\s*1937\s*$")
        self.assertIn("test_folder", block)

    # ---------------- 13. event ----------------

    def test_13_event_add(self):
        self.post_ok("/api/event_add", {"root": self.mod, "id": "tst_ns.1"})
        path = self.mod_file("events", "zz_focus_editor_events.txt")
        self.assertTrue(os.path.exists(path), "事件文件没生成：%s" % path)
        text = _read_text(path)
        self.assertIn("add_namespace = tst_ns", text)
        block = _block_text(text, "country_event")
        self.assertTrue(block, "事件文件里没有 country_event：\n%s" % text)
        self.assertIn("tst_ns.1", block)

    # ---------------- 14~16. 错误路径 ----------------

    def test_14_error_missing_required_param(self):
        """缺必填参数：/api/state_save 没有 id。"""
        status, payload = POST("/api/state_save", {"fields": {"manpower": "200000"}})
        payload["_status"] = status
        self.assert_error_payload(payload, "/api/state_save(缺 id)")
        self.assertIn("数字", payload["msg"])

    def test_15_error_wrong_param_type(self):
        """参数类型不对：manpower 给了非数字。"""
        status, payload = POST("/api/state_save",
                               {"id": 1, "fields": {"manpower": "很多很多"}})
        payload["_status"] = status
        self.assert_error_payload(payload, "/api/state_save(manpower 非数字)")
        self.assertIn("人力", payload["msg"])

    def test_16_error_nonexistent_id(self):
        """不存在的 id：焦点节点不存在。"""
        status, payload = POST("/api/save", {
            "root": self.mod,
            "file": "common/national_focus/zz_bom_tree.txt",
            "id": "NO_SUCH_FOCUS",
            "fields": {"x": 1},
        })
        payload["_status"] = status
        self.assert_error_payload(payload, "/api/save(节点不存在)")
        self.assertIn("NO_SUCH_FOCUS", payload["msg"])

        # 报错时不能把文件改坏
        text = _read_text(self.mod_file("common", "national_focus", "zz_bom_tree.txt"))
        self.assertIn("TST_alpha_2", text)

    # ---------------- 17~20. 四个回归锚点 ----------------

    def test_17_f7_bom_focus_file_both_trees(self):
        """F7：带 BOM 的国策文件要被完整解析，两棵树都在。"""
        body = self.api_get("/api/data")
        trees = {t["id"]: t for t in body["trees"]}
        self.assertIn("tree_alpha", trees, "带 BOM 的国策文件里的树丢了：%s" % sorted(trees))
        self.assertIn("tree_beta", trees, "第二棵树丢了（只解析到第一棵）：%s" % sorted(trees))
        for tid in ("tree_alpha", "tree_beta"):
            got = trees[tid]["file"].replace("\\", "/")
            self.assertEqual(got, "common/national_focus/zz_bom_tree.txt",
                             "%s 的 file 不对：%s" % (tid, trees[tid]["file"]))
        self.assertEqual([f["id"] for f in trees["tree_alpha"]["focuses"]],
                         ["TST_alpha_1", "TST_alpha_2"])
        self.assertEqual([f["id"] for f in trees["tree_beta"]["focuses"]], ["TST_beta_1"])
        # 文件本身仍然是 BOM 开头（F7 的另一半：写回不吃 BOM）
        self.assertTrue(_read_bytes(
            self.mod_file("common", "national_focus", "zz_bom_tree.txt")
        ).startswith(b"\xef\xbb\xbf"))

    def test_18_f8_delete_completed_focus_no_dangling_key(self):
        """F8：删掉一条「开局已完成国策」，不能留下只有键名没有块的残行。"""
        hist = self.mod_file("history", "countries", "TST - Test.txt")
        before = self.api_post("/api/completed_focuses", {"root": self.mod, "tag": "TST"})
        self.assertIs(before.get("ok"), True, "completed_focuses 失败：%s" % before)
        self.assertEqual(before["count"], 1,
                         "夹具里那条 complete_national_focus 没被读出来：%s" % before)
        self.assertIn("TST_alpha_1", json.dumps(before["items"], ensure_ascii=False))

        body = self.post_ok("/api/focus_complete_delete",
                            {"root": self.mod, "tag": "TST", "index": 0})
        self.assertIn("TST_alpha_1", json.dumps(body, ensure_ascii=False))

        raw = _read_bytes(hist)
        text = raw.decode("utf-8-sig")
        self.assertNotIn("complete_national_focus", text,
                         "删除后文件里还留着 complete_national_focus 的残迹：\n%s" % text)
        self.assertFalse(re.search(r"(?m)^[\t ]*complete_national_focus[\t ]*=\s*$", text),
                         "留下了悬空键名（只有键名没有 {）：\n%s" % text)
        # 同一文件里的其它内容不能被误删
        self.assertIn("set_technology = {", text)
        self.assertIn("infantry_weapons = 1", text)
        self.assertNotIn("focus", text, "删除后还留着 focus 相关内容：\n%s" % text)
        self.assertTrue(text.rstrip().endswith("}"),
                        "删除后文件结构被写坏了：\n%r" % text[-80:])

        after = self.api_post("/api/completed_focuses", {"root": self.mod, "tag": "TST"})
        self.assertIs(after.get("ok"), True, "删除后 completed_focuses 崩了：%s" % after)
        self.assertEqual(after["count"], 0, "删除后还剩 %s 条：%s" % (after.get("count"), after))

    def test_19_s1_state_detail_victory_points_none(self):
        """S1：州没有 victory_points 时详情接口不能崩（读、写两条路径）。"""
        body = self.api_get("/api/state", id=1)
        self.assertIs(body.get("ok"), True,
                      "victory_points 为空时详情崩了：%s"
                      % json.dumps(body, ensure_ascii=False)[:400])
        self.assertEqual(body["victory_points"], [],
                         "victory_points 不是空数组而是 %r" % (body["victory_points"],))
        # 只是读了一次详情，不该把 victory_points 凭空写进文件
        path = self.mod_file("history", "states", "1-test.txt")
        self.assertNotIn("victory_points", _read_text(path),
                         "读了一次详情就把 victory_points 写进文件了")

        # 写路径：解析结果为空的州，写入胜利点时也不能崩
        saved = self.post_ok("/api/state_save",
                             {"id": 1, "fields": {"victory_points": [[2, 10]]}})
        self.assertTrue(saved.get("diff"), "写胜利点没返回 diff：%s" % saved)
        history = _block_text(_read_text(path), "history")
        self.assertTrue(history, "写完胜利点后 history 块不见了")
        self.assertIn("victory_points = {", history,
                      "胜利点没落在 history 块内：\n%s" % history)
        self.assertIn("2 10", history)
        after = self.api_get("/api/state", id=1)
        self.assertEqual(after["victory_points"], [[2, 10]])

    def test_20_f13_prune_missing_root(self):
        """F13：加载前把已经不存在的根目录剔除。"""
        # 1) 造一个额外的合法 mod 并加载进来
        extra = os.path.join(self.tmpdir, "Extra Mod")
        build_min_mod(extra, tree_text=EXTRA_TREE_TEXT, tag="EXT", tree_name="zz_extra.txt")
        self.post_ok("/api/load_mod", {"path": extra})
        data = self.api_get("/api/data")
        paths = [os.path.normcase(r["path"]) for r in data["roots"]]
        self.assertIn(os.path.normcase(extra), paths, "load_mod 没把目录加进 roots：%s" % paths)

        # 2) 把它从磁盘上删掉，再加载一个新目录 —— load_mod 内部会先 _prune_roots
        shutil.rmtree(extra, ignore_errors=True)
        third = os.path.join(self.tmpdir, "Third Mod")
        build_min_mod(third, tree_text=THIRD_TREE_TEXT, tag="THD", tree_name="zz_third.txt")
        self.post_ok("/api/load_mod", {"path": third})

        data = self.api_get("/api/data")
        paths = [os.path.normcase(r["path"]) for r in data["roots"]]
        self.assertNotIn(os.path.normcase(extra), paths,
                         "已经不存在的根目录还留在 roots 里：%s" % paths)
        self.assertIn(os.path.normcase(third), paths, "新目录没进 roots：%s" % paths)
        self.assertIn(os.path.normcase(self.mod), paths, "夹具被顺手剔掉了：%s" % paths)
        # 服务本身不能被打挂
        self.api_get("/api/states")

    def test_21_prefix_route_order(self):
        """前缀路由顺序锁。

        `xuerong/api/router.py` 的 `dispatch_get` 先查精确表，未命中再按
        `GET_PREFIXES` 的注册顺序逐个 `startswith`，命中第一个就返回。也就是说
        顺序本身就是优先级：谁排在前面，谁先吃掉匹配到它的路径。

        `/api/data` 排第三，所以 `/api/database` 这类路径当前会被它截走。这是既有
        行为，不能因为搬文件而改变。

        HTTP 层面测不出顺序：这 6 个前缀两两不重叠，把任意两个调换，请求结果都一样。
        所以这里直接查运行时表。表定义在 `xuerong/api/router.py`，由各 handler 模块
        在被 import 时通过 `@prefix(...)` 装饰器注册——**注册顺序 = import 顺序 ×
        模块内定义顺序**，两者任一改动都可能把顺序打乱。
        """
        sys.path.insert(0, WORK_DIR)
        import xuerong.api.routes_get        # noqa: F401  触发前缀注册
        from xuerong.api import router

        got = [p for p, _fn in router.GET_PREFIXES]
        self.assertEqual(got, EXPECTED_PREFIX_ORDER,
                         "前缀路由顺序被打乱了。GET_PREFIXES 的注册顺序就是匹配优先级，\n"
                         "改顺序会让 /api/data 之类的宽前缀截走本该由别的路由处理的请求。\n"
                         "实际：%s\n期望：%s" % (got, EXPECTED_PREFIX_ORDER))

        # 每一条都得真能响应：顺序对了但某条丢了，同属破线。
        # 探针给真实相对路径，别拿目录本身去请求（会 500，见 rp_icons 的 isfile 判断）。
        probes = {
            "/index": "/index",
            "/help": "/help",
            "/api/data": "/api/data",
            "/icons/": "/icons/",
            "/web/": "/web/js/90-boot.js",
            "/mascot/": "/mascot/",
        }
        for prefix in EXPECTED_PREFIX_ORDER:
            url = probes[prefix]
            status, _payload = GET(url)
            self.assertIn(status, (200, 404),
                          "前缀路由 %s 的探针 %s 返回 HTTP %s" % (prefix, url, status))


def main():
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(HttpContractTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    total = result.testsRun
    bad = len(result.failures) + len(result.errors)
    print("== %d PASS / %d FAIL ==" % (total - bad, bad))
    return 0 if (bad == 0 and total == EXPECTED_CASES) else 2


if __name__ == "__main__":
    sys.exit(main())
