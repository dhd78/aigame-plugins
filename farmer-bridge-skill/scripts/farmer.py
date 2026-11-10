#!/usr/bin/env python
"""FarmerBridge client for The Farmer Was Replaced.

Reads the farm state and writes/runs game code through the local BepInEx
bridge on 127.0.0.1:15800. No screenshots, mouse or keyboard events.

Usage:
  python farmer.py state
  python farmer.py grid --x 0 --y 0 --w 8 --h 8
  python farmer.py code "print('hello')"
  python farmer.py code --file main.py
  python farmer.py run
  python farmer.py output
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:15800"

HELP_DOWN = """连不上 FarmerBridge（{base}）。
请按顺序检查：
1. 游戏《The Farmer Was Replaced》是否已启动并进入存档？
2. 是否安装了 BepInEx 5.4.23.6 (x64)，并把 FarmerBridge.dll 放进
   <游戏目录>\\BepInEx\\plugins\\？
3. 打开 <游戏目录>\\BepInEx\\LogOutput.log，搜索
   "FarmerBridge listening on 127.0.0.1:15800"。
详见 references/INSTALL.md。""".format(base=BASE)


class BridgeError(Exception):
    pass


def api(path, method="GET", body=None, timeout=8):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as error:
        try:
            detail = error.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        raise BridgeError("FarmerBridge 返回 HTTP {}{}".format(
            error.code, ": " + detail.strip() if detail.strip() else ""))
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        raise BridgeError(HELP_DOWN)


def build_parser():
    parser = argparse.ArgumentParser(description="FarmerBridge local client")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("state", help="read full farm state")
    sub.add_parser("drones", help="read drones")
    sub.add_parser("items", help="read item counts")
    sub.add_parser("unlocks", help="read unlocks")
    sub.add_parser("output", help="read game output")
    sub.add_parser("execution", help="read execution status")
    sub.add_parser("files", help="list code files")
    sub.add_parser("tech", help="read tech tree")
    sub.add_parser("stop", help="stop running code")
    sub.add_parser("step", help="single-step running code")
    sub.add_parser("save", help="save the game")
    sub.add_parser("load", help="load the current save")

    p = sub.add_parser("grid", help="read a grid rectangle")
    p.add_argument("--x", type=int, default=0)
    p.add_argument("--y", type=int, default=0)
    p.add_argument("--w", type=int, default=8)
    p.add_argument("--h", type=int, default=8)
    p.add_argument("--depth", type=int, default=-1, help="underground depth; omit for surface")

    p = sub.add_parser("code", help="write code to a file page")
    p.add_argument("source", nargs="?")
    p.add_argument("--file")
    p.add_argument("--name", default="main")

    p = sub.add_parser("file", help="create/select a code file")
    p.add_argument("name")

    p = sub.add_parser("run", help="run a code file")
    p.add_argument("--name", default="main")

    p = sub.add_parser("doc", help="read a game doc page")
    p.add_argument("page", nargs="?", default="docs/home.md")

    p = sub.add_parser("buy", help="buy a tech node (spends materials)")
    p.add_argument("name")

    p = sub.add_parser("start", help="load a save and enter the game")
    p.add_argument("--save", default="")

    return parser


def run(args):
    if args.cmd == "state":
        return api("/state")
    if args.cmd == "drones":
        return api("/drones")
    if args.cmd == "items":
        return api("/items")
    if args.cmd == "unlocks":
        return api("/unlocks")
    if args.cmd == "output":
        return api("/output")
    if args.cmd == "execution":
        return api("/execution")
    if args.cmd == "files":
        return api("/files")
    if args.cmd == "tech":
        return api("/tech")
    if args.cmd == "run":
        return api("/run", "POST", {"file": args.name})
    if args.cmd == "stop":
        return api("/stop", "POST", {})
    if args.cmd == "step":
        return api("/step", "POST", {})
    if args.cmd == "save":
        return api("/save", "POST", {})
    if args.cmd == "load":
        return api("/load", "POST", {})
    if args.cmd == "start":
        return api("/start", "POST", {"save": args.save})
    if args.cmd == "file":
        return api("/file", "POST", {"name": args.name})
    if args.cmd == "grid":
        query = urllib.parse.urlencode({"x": args.x, "y": args.y, "w": args.w, "h": args.h})
        if args.depth >= 0:
            query += "&depth=" + str(args.depth)
        return api("/grid?" + query)
    if args.cmd == "doc":
        return api("/doc?page=" + urllib.parse.quote(args.page, safe=""))
    if args.cmd == "buy":
        return api("/buy", "POST", {"name": args.name})
    if args.cmd == "code":
        source = args.source
        if args.file:
            with open(args.file, encoding="utf-8-sig") as handle:
                source = handle.read()
        if source is None:
            raise BridgeError("code 需要 source 参数或 --file <path>")
        return api("/code", "POST", {"file": args.name, "source": source})
    raise BridgeError("未知命令：" + args.cmd)


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = run(args)
    except BridgeError as error:
        print("错误：" + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
