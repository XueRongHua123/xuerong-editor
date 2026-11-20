# -*- coding: utf-8 -*-
"""全量路由冒烟：213 条 /api 路由各发一次最小请求，和金标准基线比差异。

为什么要这个东西
----------------
1. `qa/regress_all.py` 是进程内直调，一个路由都没走过 HTTP。
2. `tests/test_http_contract.py` 只覆盖 20 条（213 条的 9%），够用来验收具体功能，
   不够当「改完 542 处访问器调用点之后没炸」的兜底。
3. 改造（AppContext 化）的典型失败是「某条路由不报了 / 返回空」，这个脚本专抓这一类。

用法
----
    python tests/routes_smoke.py --record      # 首次或确认基线变化后：写基线
    python tests/routes_smoke.py               # 平时：和基线比，有恶化就红
    python tests/routes_smoke.py --only focus  # 只跑路径含 focus 的
    python tests/routes_smoke.py --slow        # 连慢路由一起跑（地图/AI/导出）

判定口径：**不是 500 且不返回 INTERNAL 就算通**。参数故意给最简，很多路由会返回
「缺少 xxx」的校验错误——那是正常行为，基线会把它记成 OK。真正要抓的是从 OK 变成
500/INTERNAL 的倒退。

例外是「写盘型」路由：它们拿到空字符串会在 int("") / io.open("") 上直接抛异常，
永远停在 INTERNAL，等于一条回归检测能力都没有（坏了也是红的，好了也是红的）。
这类路由由 `_fixture_args()` 按路由填夹具里真实存在的文件与 id，让它们走到
真正的读写路径；夹具 mod 在 tempdir 里，跑完连目录一起删。

跑完会还原 cache/options.json、本次新增的 history 快照与临时夹具，
不碰用户真实 mod 目录。
"""

import copy
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.dirname(HERE)
FOCUS_EDITOR = os.path.join(WORK_DIR, "focus_editor.py")
OPTIONS_PATH = os.path.join(WORK_DIR, "cache", "options.json")
PLAYSET_FILE = os.path.join(WORK_DIR, "playset.json")
UPDATE_CACHE = os.path.join(WORK_DIR, "cache", "update.json")
AI_CONFIG = os.path.join(WORK_DIR, "ai_config.json")

# 冒烟会碰到这些文件：开关缓存、播放集、版本检查缓存、AI 配置。
# 全部先备份、跑完原样写回——测试不许留下痕迹。
# （ai_config.json 是 /api/ai_save 的落点，里面存 API Key，绝不能被测试改写。）
MUTABLE_FILES = (OPTIONS_PATH, PLAYSET_FILE, UPDATE_CACHE, AI_CONFIG)
BASELINE = os.path.join(HERE, "routes_baseline.json")

HOST = "127.0.0.1"
READY_TIMEOUT = 300.0
FAST_TIMEOUT = 20.0
SLOW_TIMEOUT = 240.0

# 这些路由会真起长任务（建地图 / 调外部 AI / 导出整包 / 弹原生对话框），
# 默认跳过，--slow 才跑。pick_mod 会阻塞在 Windows 文件选择框上，永不返回。
SLOW_PATHS = (
    "/api/map_generate", "/api/world_create", "/api/ai_test", "/api/ai_stream",
    "/api/ai_chat", "/api/export", "/api/publish/export", "/api/map_build",
    "/api/transcribe", "/api/pick_mod", "/api/playset_pick",
    "/api/game_verify/start",
)

# 这些路由要真连外网（GitHub Release API + 下载 22 MB 附件），耗时取决于网速，
# 不能用 FAST_TIMEOUT。实测 update_apply 单次 75 秒（2026-11-17，22 MB 包），
# 而它本身不是长任务、也不该跳过——跳掉就测不到"更新链路还在不在"。
# 给它们 SLOW_TIMEOUT，与"真起长任务"区分开：这两类都慢，但原因不同。
NET_PATHS = (
    "/api/update", "/api/update_check", "/api/update_apply",
)

# 静态前缀路由：给一条真实存在的相对路径，别拿目录本身去请求。
PREFIX_PROBES = {
    "/index": "",
    "/help": "",
    "/api/data": "",
    "/web/": "/web/js/90-boot.js",
    "/icons/": "/icons/",
    "/mascot/": "/mascot/",
}


# ------------------------------------------------------------------ HTTP

def _timeout_for(path):
    """按路由挑超时：要真连外网的给 SLOW_TIMEOUT。

    update_apply 会下载 22 MB 的 release 附件，实测 75 秒；用 FAST_TIMEOUT 会在
    网慢时超成 DEAD，看着像代码回归，实际是等待不够。
    """
    for p in NET_PATHS:
        if path == p or path.startswith(p):
            return SLOW_TIMEOUT
    return FAST_TIMEOUT


def _http(method, path, body=None, timeout=FAST_TIMEOUT):
    url = "http://%s:%d%s" % (HOST, _PORT, path)
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:                      # 超时、连接被断
        return 0, ("__ERR__ " + repr(e)).encode("utf-8", "replace")


def _classify(status, raw):
    """把一次响应归成 OK / INTERNAL / HTTP500 / DEAD，并带回一句原话。

    原话很重要：同样叫 INTERNAL，有的是「缺少字段 xxx」的校验拦截（正常），
    有的是 KeyError/NameError（真 bug）。基线里带上它，改造后一眼能分清。
    """
    if status == 0:
        return "DEAD", raw.decode("utf-8", "replace")[:200]
    text = raw.decode("utf-8", "replace")
    try:
        payload = json.loads(text)
    except Exception:
        payload = None
    msg = ""
    if isinstance(payload, dict):
        for k in ("message", "msg", "error", "detail", "code"):
            v = payload.get(k)
            if isinstance(v, str) and v:
                msg = v
                break
    if not msg:
        msg = text[:200]
    msg = msg.replace("\n", " ")[:200]
    if status >= 500:
        if '"code": "INTERNAL"' in text or '"code":"INTERNAL"' in text:
            return "INTERNAL", msg
        return "HTTP500", msg
    return "OK", msg


# ------------------------------------------------------- 路由清单（运行时）

def load_routes():
    """直接读运行时的三张路由表，这是唯一权威的覆盖率分母。"""
    sys.path.insert(0, WORK_DIR)
    import xuerong.api.routes_post        # noqa: F401  注册用
    import xuerong.api.routes_get         # noqa: F401
    from xuerong.api import router
    out = []
    for p in sorted(router.POST_ROUTES):
        out.append({"method": "POST", "path": p})
    for p in sorted(router.GET_ROUTES):
        out.append({"method": "GET", "path": p})
    for p, _fn in router.GET_PREFIXES:
        out.append({"method": "GET", "path": p, "prefix": True})
    return out


def _route_sources():
    """路由源码清单：两个旧入口 + handlers/ 下按域拆的文件。

    P4 把 151 条 POST 的实体搬进了 handlers/，routes_post.py 只剩兼容层。
    只扫旧入口会一条参数都抽不到，POST 全用空 body，冒烟强度静默下降。
    """
    api = os.path.join(WORK_DIR, "xuerong", "api")
    out = [os.path.join(api, n) for n in ("routes_post.py", "routes_get.py")]
    hdir = os.path.join(api, "handlers")
    if os.path.isdir(hdir):
        out.extend(os.path.join(hdir, f) for f in sorted(os.listdir(hdir)) if f.endswith(".py"))
    return [p for p in out if os.path.isfile(p)]


def _params_by_path():
    """从路由源码里 AST 抽参数名，给 POST 造一个「形状对、值不对」的 body。

    不缓存成 json 文件：路由表一改，缓存就过期，过期缓存会让基线静默失真。
    每次现抽，六个文件的解析不到 100 毫秒。
    """
    import ast
    import re

    table = {}
    for path in _route_sources():
        with open(path, encoding="utf-8") as f:
            src = f.read()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        lines = src.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            routes = []
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call) or not dec.args:
                    continue
                try:
                    val = ast.literal_eval(dec.args[0])
                except Exception:
                    continue
                if isinstance(val, str) and val.startswith("/api"):
                    routes.append(val)
            if not routes:
                continue
            seg = "\n".join(lines[node.lineno - 1:node.end_lineno])
            params = sorted(set(re.findall(
                r'\b(?:body|qs|query|q|params)\s*\.\s*get\(\s*["\']([A-Za-z0-9_]+)["\']', seg)))
            for r in routes:
                table[r] = params
    return table


# 参数名 → 默认值。基线一律是空字符串，这里只登记「空字符串一定会抛异常」的那几类，
# 别的仍是 ""。判断依据是这条参数在实现里的直接用法：
#   · int(body.get("src"))   → 空串抛 invalid literal
#   · body.get("entries").items() → 空串抛 'str' object has no attribute 'items'
# 不按路由写特殊值——那是 `_fixture_args()` 的活，这里只管类型。
_ARG_DEFAULTS = {
    # 整数型参数：路由直接 int(body.get(...))，空串抛 invalid literal
    "index": "-1",
    "src": "0",
    "dst": "0",
    # 容器型参数：路由对它们 .items() / 迭代元素，空串抛 AttributeError
    "entries": {},
    "props": {},
    "options": [],
}


def _min_body(params):
    """给每个已知参数一个占位值。

    默认一律给字符串：这一版实现里大量路由对 `id` 直接 `.strip()`，给 int 会抛
    `'int' object has no attribute 'strip'`——那是夹具的错，不是路由的错，
    会把真正的失败淹掉（第一版就是这么被误导的）。

    只有 `_ARG_DEFAULTS` 登记过的参数名换掉，且仍然保持「能给最小值」的原则。
    可变默认值必须深拷贝：同一份 dict 被两个路由共用时，前一个改了会影响后一个。
    """
    return {name: copy.deepcopy(_ARG_DEFAULTS.get(name, "")) for name in params}


# ------------------------------------------------------------- 服务管理

_PORT = 0


def _pick_port():
    import socket
    s = socket.socket()
    s.bind((HOST, 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _snap_file(path):
    if os.path.isfile(path):
        with open(path, "rb") as f:
            return f.read()
    return None


def _restore_file(path, data):
    if data is None:
        if os.path.isfile(path):
            os.remove(path)
    else:
        with open(path, "wb") as f:
            f.write(data)


def _update_dirs():
    """`/api/update` 会下载并解包一个 22 MB 的包，落在这些目录里。

    它们是目录不是文件，_snap_file 管不到，所以单独记录：跑完只删本次新增的，
    跑前就有的（用户自己留的）不动。
    """
    found = set(glob.glob(os.path.join(WORK_DIR, "_update_*")))
    pkg = os.path.join(WORK_DIR, "cache", "update_pkg")
    if os.path.isdir(pkg):
        found.add(pkg)
    return found


def _quiet_options():
    """隔离用：两个开关都关，避免 playset 把重 mod 拖进来。"""
    os.makedirs(os.path.dirname(OPTIONS_PATH), exist_ok=True)
    with open(OPTIONS_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"follow_deps": False, "follow_launcher": False}, f)


# 夹具里每个文件承载哪些实体。`_fixture_args()` 按表取真实 id 与整块脚本，
# 三处（造文件 / 挑 id / 抽 raw）读同一份定义，不会各写各的。
#
#   file    —— 相对 mod 根的路径，必须和产品的 loader 认的目录一致；
#   extract —— 从文件里定位块的方式：direct 是 `<id> = {`，event 是块内 `id = <eid>`；
#   save / delete / link / shared / default —— 各条路由要的那个实体。
_FIXTURE_SPECS = {
    "ideas": {"file": "common/ideas/smoke_ideas.txt", "extract": "direct",
              "save": "SMK_smoke_idea", "delete": "SMK_idea_del"},
    "equipment": {"file": "common/units/equipment/smoke_equipment.txt", "extract": "direct",
                  "save": "SMK_equip_save", "delete": "SMK_equip_del"},
    "technologies": {"file": "common/technologies/smoke_tech.txt", "extract": "direct",
                     "save": "SMK_tech_a", "delete": "SMK_tech_del",
                     "link": ("SMK_tech_b", "SMK_tech_c")},
    "events": {"file": "events/smoke_events.txt", "extract": "event",
               "save": "smoke.saved", "delete": "smoke.del"},
    "national_focus": {"file": "common/national_focus/smoke_focus.txt", "extract": "direct",
                       "save": "smoke_tree", "shared": "smoke_shared", "default": "no"},
}

# 夹具 mod 的文件内容。每条都要能被产品 loader 正常解析——save 之后会 _reload()
# 重扫整个 mod，一个畸形文件会让「保存成功」变成「保存后崩」。
_FIXTURE_FILES = {
    "common/ideas/smoke_ideas.txt": """ideas = {
	country = {
		SMK_smoke_idea = {
			picture = GFX_idea_smoke
			modifier = {
				war_support_factor = 0.05
			}
		}
		SMK_idea_del = {
			picture = GFX_idea_smoke
		}
	}
}
""",
    "common/units/equipment/smoke_equipment.txt": """equipments = {
	SMK_equip_save = {
		year = 1936
		is_buildable = yes
		type = infantry
		build_cost_ic = 1.0
	}
	SMK_equip_del = {
		year = 1936
		type = infantry
	}
}
""",
    "common/technologies/smoke_tech.txt": """technologies = {
	smoke_folder = {
		SMK_tech_a = {
			research_cost = 1
			start_year = 1936
			folder = {
				name = smoke_folder
				position = { x = 0 y = 0 }
			}
			path = {
				leads_to_tech = SMK_tech_b
				research_cost_coeff = 1
			}
		}
		SMK_tech_b = {
			research_cost = 1
			start_year = 1936
			folder = {
				name = smoke_folder
				position = { x = 1 y = 0 }
			}
		}
		SMK_tech_c = {
			research_cost = 1
			start_year = 1936
			folder = {
				name = smoke_folder
				position = { x = 2 y = 0 }
			}
		}
		SMK_tech_del = {
			research_cost = 1
			start_year = 1936
			folder = {
				name = smoke_folder
				position = { x = 3 y = 0 }
			}
		}
	}
}
""",
    "events/smoke_events.txt": """add_namespace = smoke

country_event = {
	id = smoke.del
	title = smoke.del.t
	desc = smoke.del.d
	is_triggered_only = yes
	option = {
		name = smoke.del.a
	}
}

country_event = {
	id = smoke.saved
	title = smoke.saved.t
	desc = smoke.saved.d
	is_triggered_only = yes
	option = {
		name = smoke.saved.a
	}
}
""",
    "common/national_focus/smoke_focus.txt": """focus_tree = {
	id = smoke_tree
	country = {
		factor = 0
		modifier = {
			add = 10
			tag = SMK
		}
	}
	default = no
	focus = {
		id = SMK_focus_a
		x = 0
		y = 0
		cost = 10
		completion_reward = {
			add_political_power = 50
		}
	}
}

shared_focus = {
	id = smoke_shared
	x = 0
	y = 0
	cost = 10
}
""",
}


def _make_fixture(tmp):
    """最小 mod 夹具：国家标签 + 州目录 + 五种可编辑实体。

    实体本身是必需的，不是锦上添花：写盘型路由（idea_save / tech_link /
    save_tree 这些）要拿真实的 file 与 id 才能在夹具里走完「定位 → 改块 → 写盘」
    全程。只给空字符串的话它们停在 int("") / io.open("")，永远返回 INTERNAL，
    等于这些路由没有回归检测能力——坏了也是同一个红，看不出来。

    所有内容都落在 tempdir 里，跑完随目录一起删。
    """
    mod = os.path.join(tmp, "smoke_mod")
    os.makedirs(os.path.join(mod, "common", "country_tags"))
    os.makedirs(os.path.join(mod, "history", "states"))
    with open(os.path.join(mod, "common", "country_tags", "00_tags.txt"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write('SMK = "common/country_tags/smk.txt"\n')
    with open(os.path.join(mod, "descriptor.mod"), "w", encoding="utf-8", newline="\n") as f:
        f.write('name="smoke"\nversion="0.0.1"\n')
    for rel, text in _FIXTURE_FILES.items():
        path = os.path.join(mod, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return mod


def _brace_end(text, i):
    """从 i 处的 `{` 找到配对 `}` 之后的位置（与 xuerong.core.text.brace_match 同语义）。"""
    depth, instr = 0, False
    while i < len(text):
        c = text[i]
        if c == '"':
            instr = not instr
        elif not instr:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return i


def _fixture_block(root, spec):
    """从夹具文件里抽出 `<实体> = {…}` 整块，形状和 `/api/raw` 返回的一致。

    保存接口吃的就是这个形状：前端把 `/api/raw` 的 `raw` 原样回传，服务端拿它
    替换原块。夹具里另造一份别的形状，测的就不是真实链路了。
    """
    path = os.path.join(root, spec["file"].replace("/", os.sep))
    with open(path, encoding="utf-8") as f:
        text = f.read()
    ident = re.escape(spec["save"])
    if spec["extract"] == "event":
        m = re.search(r'(?m)^[ \t]*id\s*=\s*"?%s"?' % ident, text)
        # 事件块的键是 country_event 这种，id 只是块内一行：从 id 往前退到块首
        start = text.rfind("_event", 0, m.start())
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
            start -= 1
        start = text.rfind("\n", 0, start) + 1
    else:
        start = re.search(r'(?m)^[ \t]*%s\s*=\s*\{' % ident, text).start()
    return text[start:_brace_end(text, text.find("{", start))]


# 写盘型路由 → (夹具实体, 用法)。用法决定填哪几个参数：
#   save   实体整块改写 → root/file/id/raw
#   delete 删实体       → root/file/id
#   link   加前置       → root/file/source/target
#   tree   树设置       → root/file/id/default/country_raw
#   shared 删共享焦点   → root/file/id
_WRITE_ROUTES = {
    "/api/idea_save": ("ideas", "save"),
    "/api/delete_idea": ("ideas", "delete"),
    "/api/equip_save": ("equipment", "save"),
    "/api/equip_delete": ("equipment", "delete"),
    "/api/tech_save": ("technologies", "save"),
    "/api/tech_delete": ("technologies", "delete"),
    "/api/tech_link": ("technologies", "link"),
    "/api/event_save": ("events", "save"),
    "/api/event_delete": ("events", "delete"),
    "/api/save_tree": ("national_focus", "tree"),
    "/api/shared_delete": ("national_focus", "shared"),
}

# 参数不由实体决定的三条，直接给字面值。
#   loc_save      entries 空 dict，save_loc 遍历 items 不崩、不写盘；root 仍指夹具。
#   repair_braces 只认 ROOTS 里存在的相对路径：给夹具里花括号本来就平衡的文件，
#                 它在写盘之前就返回「本来就是平衡的」，无副作用。
#   restore_backup index 给 -1 必然落在「备份不存在」，也不写盘。
#   map_merge     act 走 preview、两个不同的省号：缺 definition.csv 时返回
#                 「省 1 在 definition.csv 里没有定义」，是正常的 ok:false。
_FIXTURE_EXTRA = {
    "/api/loc_save": {"entries": {}},
    "/api/map_merge": {"act": "preview", "src": "1", "dst": "2"},
    "/api/repair_braces": {"file": "common/ideas/smoke_ideas.txt"},
    "/api/restore_backup": {"file": "common/ideas/smoke_ideas.txt", "index": "-1"},
}


def _fixture_args(mod_root):
    """写盘型路由的参数：指向夹具 mod 里真实存在的文件与 id。

    为什么不在 `_min_body` 里直接写死：夹具 mod 的绝对路径要等 `tempfile.mkdtemp()`
    之后才知道，`root` 只能是运行时值。更不能给空字符串——`os.path.join("", rel)`
    会落到 `work/` 真实目录，测试写坏用户的仓库。

    返回 {路由: {参数名: 值}}，由 `run()` 覆盖合并到 `_min_body()` 的结果上。
    """
    out = {}
    for path, (kind, use) in _WRITE_ROUTES.items():
        spec = _FIXTURE_SPECS[kind]
        args = {"root": mod_root, "file": spec["file"]}
        if use == "save":
            args["id"] = spec["save"]
            args["raw"] = _fixture_block(mod_root, spec)
        elif use == "delete":
            args["id"] = spec["delete"]
        elif use == "link":
            args["source"], args["target"] = spec["link"]
        elif use == "tree":
            args["id"] = spec["save"]
            args["default"] = spec["default"]
            args["country_raw"] = ""
        elif use == "shared":
            args["id"] = spec["shared"]
        out[path] = args
    for path, args in _FIXTURE_EXTRA.items():
        out[path] = dict(args, root=mod_root)
    return out


# 注入假 webbrowser，避免起服务时弹浏览器；argv 在子进程里直接给定。
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


def start_server(mod_root, game_root):
    global _PORT
    _PORT = _pick_port()
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    argv = ["focus_editor.py", "--mod", mod_root, "--game", game_root, "--port", str(_PORT)]
    boot = BOOT_TEMPLATE % (argv, FOCUS_EDITOR)
    log = open(os.path.join(tempfile.gettempdir(), "routes_smoke_server.log"), "wb")
    proc = subprocess.Popen(
        [sys.executable, "-X", "utf8", "-c", boot],
        cwd=WORK_DIR, env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    t0 = time.time()
    while time.time() - t0 < READY_TIMEOUT:
        if proc.poll() is not None:
            raise SystemExit("服务进程提前退出，看日志：%s" % log.name)
        code, _ = _http("GET", "/api/data", timeout=5.0)
        if code == 200:
            return proc
        time.sleep(1.5)
    proc.kill()
    raise SystemExit("服务 %d 秒内没就绪" % int(READY_TIMEOUT))


# ------------------------------------------------------------------ 主流程

def _sanitize(msg):
    """把本机绝对路径换成占位符再落进基线。

    基线是要进仓库的文件，里面出现 `C:\\Users\\<用户名>` 或工作区绝对路径不合适；
    而且这些临时路径每次跑都不同，不去掉的话基线永远对不上。
    """
    import re

    for raw, tag in ((tempfile.gettempdir(), "<TMP>"), (WORK_DIR, "<WORK>")):
        if raw:
            msg = msg.replace(raw, tag)
            msg = msg.replace(raw.replace("\\", "/"), tag)
    # 其余盘符下的用户目录（Paradox 存档目录、数据目录一类）
    msg = re.sub(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\"'\s]+", "<USERPROFILE>", msg)
    msg = re.sub(r"[A-Za-z]:[\\/]+[^\\/\"'\s]*工作区[\\/]", "<WORKSPACE>\\\\", msg)
    return msg


def _history_dir():
    """写盘型路由会调 snapshot()，把被改文件复制到 work/history/ 留作撤销用。"""
    return os.path.join(WORK_DIR, "history")


def _history_files():
    d = _history_dir()
    if not os.path.isdir(d):
        return set()
    return set(n for n in os.listdir(d) if n.endswith(".txt"))


def _history_cleanup(before):
    """只删本次运行新增的快照。

    跑前就在的文件不动——那是用户自己编辑留下的撤销记录，删了等于替他丢数据。
    快照内容是夹具 mod 的临时文件，随 tempdir 一起失效，留着也是垃圾。
    """
    d = _history_dir()
    for name in sorted(_history_files() - before):
        try:
            os.remove(os.path.join(d, name))
        except OSError:
            pass


def run(record=False, only=None, slow=False):
    # /api/playset_save 会真写 work/playset.json、/api/update 会写 cache/update.json。
    # 不备份就等于跑一次测试清空一次用户的播放集、改一次版本缓存——第一版漏了这一步。
    saved = {p: _snap_file(p) for p in MUTABLE_FILES}
    dirs_before = _update_dirs()
    history_before = _history_files()
    _quiet_options()
    tmp = tempfile.mkdtemp(prefix="smoke_")
    proc = None
    try:
        mod = _make_fixture(tmp)
        game = os.path.join(tmp, "game")
        os.makedirs(os.path.join(game, "common", "country_tags"), exist_ok=True)
        os.makedirs(os.path.join(game, "history", "states"), exist_ok=True)
        with open(os.path.join(game, "common", "country_tags", "00_tags.txt"), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write('SMK = "common/country_tags/smk.txt"\n')
        proc = start_server(mod, game)
        print("服务就绪：端口 %d" % _PORT)

        routes = load_routes()
        params = _params_by_path()
        fixture_args = _fixture_args(mod)
        base = {}
        if os.path.isfile(BASELINE) and not record:
            with open(BASELINE, encoding="utf-8") as f:
                _bl = json.load(f)
            # schema 2：键从「路径」改成「方法 路径」。同一个路径可能同时在
            # POST 与 GET 两张表里（/api/ai_config、/api/terrain_by_type），
            # 只按路径作键会让后跑的那条覆盖前一条，前一条的退化就查不出来。
            if _bl.get("schema") != 2:
                print("\n基线是旧格式（键里没有方法前缀），先跑 --record 重建")
                return 1
            base = _bl.get("routes", {})

        results = {}
        counts = {"OK": 0, "INTERNAL": 0, "HTTP500": 0, "DEAD": 0, "SKIP": 0}
        for i, r in enumerate(routes, 1):
            path = r["path"]
            key = "%s %s" % (r["method"], path)
            if only and only not in path:
                continue
            if not slow and any(path.startswith(s) for s in SLOW_PATHS):
                results[key] = {"method": r["method"], "state": "SKIP", "status": 0, "msg": ""}
                counts["SKIP"] += 1
                continue
            if r.get("prefix"):
                probe = path + PREFIX_PROBES.get(path, "")
                code, raw = _http("GET", probe, timeout=_timeout_for(path))
            elif r["method"] == "POST":
                body = _min_body(params.get(path, []))
                # 写盘型路由的夹具值覆盖占位值：它们拿到空字符串只会停在
                # int("") / io.open("")，永远 INTERNAL，等于没有回归检测能力。
                body.update(fixture_args.get(path, {}))
                code, raw = _http("POST", path, body, timeout=_timeout_for(path))
            else:
                code, raw = _http("GET", path, timeout=_timeout_for(path))
            state, msg = _classify(code, raw)
            # 只给失败留原话：成功响应体里常有本机绝对路径（导入目录 / 日志路径），
            # 存进仓库既没必要也不合适；失败原话才是排查要看的。
            results[key] = {"method": r["method"], "state": state, "status": code,
                            "msg": _sanitize(msg) if state != "OK" else ""}
            counts[state] += 1
            if i % 25 == 0:
                print("  ... %d/%d" % (i, len(routes)))

        # counts 以明细为准：路由表里同一路径可能出现两次（POST 与 GET 同名），
        # 逐次累加会把它算两遍（190 vs 188），这里按「方法 + 路径」的唯一键重算。
        counts = {"OK": 0, "INTERNAL": 0, "HTTP500": 0, "DEAD": 0, "SKIP": 0}
        for _v in results.values():
            counts[_v["state"]] = counts.get(_v["state"], 0) + 1
        total = sum(v for k, v in counts.items() if k != "SKIP")
        print("\n=== 结果（%d 条实跑 / %d 条跳过，共 %d 次调用）===" % (
            total, counts["SKIP"], total + counts["SKIP"]))
        for k in ("OK", "INTERNAL", "HTTP500", "DEAD"):
            print("  %-9s %3d" % (k, counts[k]))

        if record:
            with open(BASELINE, "w", encoding="utf-8", newline="\n") as f:
                json.dump({"schema": 2,
                           "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                           "counts": counts, "routes": results}, f,
                          ensure_ascii=False, indent=1)
            print("\n基线已写入 %s" % BASELINE)
            return 0

        if not base:
            print("\n没有基线文件，先跑 --record")
            return 1

        bad = []
        for path, cur in sorted(results.items()):
            if cur["state"] == "SKIP":
                continue
            old = base.get(path)
            if old is None:
                bad.append((path, "NEW", cur["state"]))
                continue
            if old["state"] == "OK" and cur["state"] != "OK":
                bad.append((path, old["state"], cur["state"]))
            elif old["state"] != "OK" and cur["state"] == "OK":
                print("  改善 %-34s %s -> OK" % (path, old["state"]))

        if bad:
            print("\n=== 倒退 %d 条 ===" % len(bad))
            for path, old, new in bad:
                print("  %-38s %s -> %s" % (path, old, new))
            return 2

        print("\n与基线一致，无倒退。")
        return 0
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except Exception:
                proc.kill()
        for _p, _data in saved.items():
            _restore_file(_p, _data)
        for _d in sorted(_update_dirs() - dirs_before):
            shutil.rmtree(_d, ignore_errors=True)
        _history_cleanup(history_before)
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    record = "--record" in argv
    slow = "--slow" in argv
    only = None
    for a in argv:
        if a.startswith("--only="):
            only = a.split("=", 1)[1]
    return run(record=record, only=only, slow=slow)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
