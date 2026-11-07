#!/usr/bin/env python
"""Minimal Senren Banka read-only bridge client.

Usage:
  python read_state.py
  python read_state.py --advance
"""
import argparse
import json
import urllib.request

BASE = "http://127.0.0.1:15528"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def post(path, body=None):
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--advance", action="store_true")
    args = ap.parse_args()

    state = get("/state")
    who = (state.get("author") or "").strip()
    text = (state.get("text") or "").strip()
    print(f"[{state.get('scene', '')}] {who + '：' if who else ''}{text}")
    print(json.dumps(state, ensure_ascii=False, indent=2))

    if args.advance:
        result = post("/advance")
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
