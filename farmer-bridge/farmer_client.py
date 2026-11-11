#!/usr/bin/env python
"""FarmerBridge client: memory-only control for The Farmer Was Replaced.

No screenshots, no virtual mouse, no keyboard events.

Usage:
  python farmer_client.py state
  python farmer_client.py grid [--x 0 --y 0 --w 8 --h 8]
  python farmer_client.py code "print('hello')"
  python farmer_client.py code --file main.py
  python farmer_client.py code --name maze --file maze.py
  python farmer_client.py files
  python farmer_client.py file maze
  python farmer_client.py run
  python farmer_client.py run --name maze
  python farmer_client.py stop
  python farmer_client.py output
  python farmer_client.py doc docs/scripting/while.md
  python farmer_client.py tech
  python farmer_client.py buy loops
"""
import argparse
import json
import urllib.request
import urllib.parse

BASE = "http://127.0.0.1:15800"


def api(path, method="GET", body=None, timeout=8):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("state")
    sub.add_parser("drones")
    sub.add_parser("items")
    sub.add_parser("unlocks")
    sub.add_parser("output")
    sub.add_parser("execution")
    p = sub.add_parser("run")
    p.add_argument("--name", default="main")
    sub.add_parser("stop")
    sub.add_parser("step")
    sub.add_parser("save")
    sub.add_parser("load")
    p = sub.add_parser("start")
    p.add_argument("--save", default="")

    p = sub.add_parser("grid")
    p.add_argument("--x", type=int, default=0)
    p.add_argument("--y", type=int, default=0)
    p.add_argument("--w", type=int, default=8)
    p.add_argument("--h", type=int, default=8)
    p.add_argument("--depth", type=int, default=-1)

    sub.add_parser("files")

    p = sub.add_parser("file")
    p.add_argument("name")

    p = sub.add_parser("doc")
    p.add_argument("page", nargs="?", default="docs/home.md")

    sub.add_parser("tech")

    p = sub.add_parser("buy")
    p.add_argument("name")

    p = sub.add_parser("code")
    p.add_argument("source", nargs="?")
    p.add_argument("--file")
    p.add_argument("--name", default="main")

    args = parser.parse_args()

    if args.cmd == "state":
        result = api("/state")
    elif args.cmd == "drones":
        result = api("/drones")
    elif args.cmd == "items":
        result = api("/items")
    elif args.cmd == "unlocks":
        result = api("/unlocks")
    elif args.cmd == "output":
        result = api("/output")
    elif args.cmd == "execution":
        result = api("/execution")
    elif args.cmd == "run":
        result = api("/run", "POST", {"file": args.name})
    elif args.cmd == "stop":
        result = api("/stop", "POST", {})
    elif args.cmd == "step":
        result = api("/step", "POST", {})
    elif args.cmd == "save":
        result = api("/save", "POST", {})
    elif args.cmd == "load":
        result = api("/load", "POST", {})
    elif args.cmd == "start":
        result = api("/start", "POST", {"save": args.save})
    elif args.cmd == "files":
        result = api("/files")
    elif args.cmd == "file":
        result = api("/file", "POST", {"name": args.name})
    elif args.cmd == "grid":
        result = api(f"/grid?x={args.x}&y={args.y}&w={args.w}&h={args.h}&depth={args.depth}")
    elif args.cmd == "doc":
        result = api("/doc?page=" + urllib.parse.quote(args.page, safe=""))
    elif args.cmd == "tech":
        result = api("/tech")
    elif args.cmd == "buy":
        result = api("/buy", "POST", {"name": args.name})
    elif args.cmd == "code":
        source = args.source
        if args.file:
            with open(args.file, encoding="utf-8-sig") as handle:
                source = handle.read()
        if source is None:
            raise SystemExit("code requires source or --file")
        result = api("/code", "POST", {"file": args.name, "source": source})
    else:
        raise SystemExit("unknown command")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
