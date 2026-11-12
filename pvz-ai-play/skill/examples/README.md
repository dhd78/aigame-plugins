# 示例

最小调用示例（Python 标准库，无额外依赖）。需要本机已启动游戏、`pvztools` 已安装、桥已运行。

```python
import json
import time
import urllib.request

BASE = "http://127.0.0.1:15580"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def post(path, body):
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


health = get("/health")
state = get("/state")
print(health["ok"], state["ui"], state["sun"])

if state["ui"] == "选卡界面":
    print(post("/pick", {"seeds": ["向日葵", "豌豆射手", "坚果"]}))
    print(post("/start", {"wait": 20}))

# 种一棵（会扣阳光、写冷却；409 时按 reason 换卡 / 换格，不要盲重试）
print(post("/plant", {"row": 0, "col": 1, "plant": "向日葵"}))
time.sleep(1.5)
```

完整主循环、409 映射与特殊关卡见 `references/AGENTS.md`；字段参考见 `references/API.md`。

## 小游戏示例（0.2.0）

```python
# 破罐者：先读罐子内容，再敲罐 / 种罐中植物
s = get("/state")
for vase in s.get("vases", []):
    print(vase["row"], vase["col"], vase.get("vase_kind"), vase.get("plant") or vase.get("zombie"))
# post("/break_vase", {"row": 3, "col": 6})
# post("/vase_plant", {"row": 4, "col": 0})

# 老虎机：拉杆 + 种奖品
# post("/spin", {})
# post("/plant_prize", {"row": 1, "col": 3, "type": 5})

# 宝石迷阵 Twist：旋转 2×2（row/col 是左上角），之后重读 /state 确认
# post("/twist_rotate", {"row": 2, "col": 3})

# 谁笑到最后：提前拉下一波
# post("/next_wave", {})
```

> `/debug_click`、`/force_plant` 是调试接口，示例不把它们放进主流程；`/begh_swap` 全屏可能失效。

> 本包不含游戏、存档或 exe；示例不会自动开始游戏。请先手动启动游戏并进入关卡。
