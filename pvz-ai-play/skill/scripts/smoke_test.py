"""冒烟测试：只验证桥进程提供的接口结构与字段，不需要真实游戏也能跑（部分）。

用法:
    python scripts/smoke_test.py [port]

退出码 0 = 通过，1 = 失败。
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 15580
BASE = f"http://127.0.0.1:{PORT}"

STATE_KEYS = ["ok", "ui", "in_level", "sun"]
SEED_KEYS = ["slot", "type", "name", "cost", "usable"]
PLANT_KEYS = ["row", "col", "type", "name"]


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def main() -> int:
    # 1) /health
    try:
        h = get("/health")
    except Exception as e:
        fail("连接不上 %s：%s" % (BASE, e))
    if not h.get("ok"):
        fail("/health 返回异常：%r" % (h,))
    print("ok  /health")

    # 2) /state 顶层字段
    try:
        s = get("/state")
    except urllib.error.HTTPError as e:
        fail("/state 返回 %s（游戏没开或版本不对）" % e.code)
    except Exception as e:
        fail("/state 请求失败：%s" % e)

    missing = [k for k in STATE_KEYS if k not in s]
    if missing:
        fail("/state 缺字段：%s" % missing)
    print("ok  /state 顶层字段")

    # 3) 结构字段（空棋盘时也要存在）
    ZOMBIE_KEYS = ["row", "x", "type", "name", "hp"]
    for key, keys in (("seeds", SEED_KEYS), ("plants", PLANT_KEYS),
                      ("zombies", ZOMBIE_KEYS)):
        items = s.get(key)
        if not isinstance(items, list):
            fail("/state.%s 不是列表" % key)
        if items:
            miss = [k for k in keys if k not in items[0]]
            if miss:
                fail("/state.%s[0] 缺字段：%s" % (key, miss))
    for key in ("blocked", "ice", "water", "lily", "pots", "vases", "belt"):
        if not isinstance(s.get(key), list):
            fail("/state.%s 应为列表" % key)
    print("ok  /state 子字段")

    # 4) 场景/关卡信息自洽
    scene = s.get("scene")
    if scene is not None and not (-1 <= int(scene) <= 5):
        fail("scene 取值异常：%r" % scene)
    if s.get("is_pool") and not s.get("water"):
        print("warn  is_pool=true 但 water 为空（可能暂不在关卡内）")
    print("ok  场景字段")

    print("\n全部通过。ui=%s in_level=%s conveyor=%s scene=%s" % (
        s.get("ui"), s.get("in_level"), s.get("conveyor"), s.get("scene")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
