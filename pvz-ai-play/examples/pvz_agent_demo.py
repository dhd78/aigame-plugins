"""PvZ1 自动游玩示例（无视觉、无鼠标）。

演示如何：
  1. 读 /state 决策
  2. 选卡 + 开局
  3. 处理普通关 / 传送带关 / 池塘 / 屋顶 / 冰面
  4. 处理 409 的各种 reason

用法:
    python pvz_agent_demo.py [秒数] [端口]

默认跑 120 秒，端口 15580。
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 15580
BASE = f"http://127.0.0.1:{PORT}"

# 起手卡组（按自己解锁情况改）
DECK = ["小喷菇", "向日葵", "豌豆射手", "坚果", "寒冰射手", "双发射手", "樱桃炸弹"]

# 种植优先级：越靠前越先种
PRIORITY = ["向日葵", "阳光菇", "小喷菇", "豌豆射手", "双发射手", "寒冰射手",
            "坚果", "大嘴花", "窝瓜", "土豆雷", "樱桃炸弹"]


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def post(path: str, body: dict, timeout: int = 40) -> tuple:
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def free_cells(s: dict) -> list:
    """可用格子：扣掉植物、障碍、冰面，再按池塘/屋顶过滤。"""
    occ = {(p["row"], p["col"]) for p in s["plants"] if p["type"] != 33}
    occ |= {(r, c) for r, c in s.get("blocked", [])}
    occ |= {(r, c) for r, c in s.get("ice", [])}

    rows = 6 if s.get("is_pool") else 5
    cells = [(r, c) for c in range(9) for r in range(rows) if (r, c) not in occ]

    # 池塘：水面必须有荷叶
    if s.get("is_pool"):
        lily = {(r, c) for r, c in s.get("lily", [])}
        water = {(r, c) for r, c in s.get("water", [])}
        cells = [cell for cell in cells if cell not in water or cell in lily]

    # 屋顶：必须踩花盆
    if s.get("scene") == 4:
        pots = {(r, c) for r, c in s.get("pots", [])}
        cells = [cell for cell in cells if cell in pots]

    return cells


def pick_card(s: dict):
    """按优先级选一张可用的卡；传送带关从 belt 里挑。"""
    if s.get("conveyor"):
        belt = s.get("belt", [])
        return belt[0] if belt else None
    by_name = {x["name"]: x for x in s["seeds"]}
    for name in PRIORITY:
        card = by_name.get(name)
        if card and card.get("usable"):
            return card
    return None


def step(s: dict) -> str:
    """执行一步，返回描述。"""
    # 1) 选卡界面
    if s.get("ui") == "选卡界面":
        code, res = post("/pick", {"seeds": DECK})
        if not res.get("ok"):
            return "pick failed: %s" % res.get("failed")
        code, res = post("/start", {"wait": 20})
        return "start: %s" % res.get("ok")

    # 2) 不在关卡
    if not s.get("in_level"):
        return "not in level"

    cells = free_cells(s)
    if not cells:
        return "no free cell"

    card = pick_card(s)
    if not card:
        return "no usable card"

    row, col = cells[0]
    code, res = post("/plant", {"row": row, "col": col, "plant": card["name"]})
    if res.get("ok"):
        return "plant %s @(%d,%d) sun=%s" % (card["name"], row, col, res.get("sun"))

    reason = res.get("reason") or res.get("error")
    if reason == "needs_lilypad":
        # 先种荷叶（如果卡组里有）
        lily = next((x for x in s["seeds"] if x["type"] == 16 and x.get("usable")), None)
        if lily:
            code, r2 = post("/plant", {"row": row, "col": col, "plant": lily["name"]})
            return "plant lily @(%d,%d) ok=%s" % (row, col, r2.get("ok"))
    return "plant %s @(%d,%d) -> %s" % (card["name"], row, col, reason)


def main(seconds: float = 120.0) -> int:
    end = time.time() + seconds
    last = ""
    while time.time() < end:
        try:
            s = get("/state")
        except Exception as e:
            print("state error:", e)
            time.sleep(2)
            continue

        line = step(s)
        if line != last:
            print("[%6.1fs] %s" % (time.time() - (end - seconds), line))
            last = line
        time.sleep(1.2)

    s = get("/state")
    print("\n=== 结束 ===")
    print("波次 %s | 阳光 %s | 植物 %d | 僵尸 %d" % (
        s.get("wave"), s.get("sun"), len(s.get("plants", [])), len(s.get("zombies", []))))
    return 0


if __name__ == "__main__":
    sys.exit(main(float(sys.argv[1]) if len(sys.argv) > 1 else 120.0))
