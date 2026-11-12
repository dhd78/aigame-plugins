# AGENTS.md — 给 AI 智能体的 PvZ1 操作手册

> 这份文件是写给 **AI 智能体** 看的。目标：读完之后你就能驱动《植物大战僵尸》1.0.0.1051 打完一关。
> 你不需要视觉、不需要 OCR、不需要鼠标。全部通过一个本地 HTTP 接口完成。

---

## 0. 一句话心智模型

```
GET /state  →  看棋盘（阳光、卡片、植物、僵尸、障碍物）
POST /plant →  种一棵（扣阳光、进冷却、失败有明确 reason）
POST /shovel→  铲一棵
POST /pick  →  选卡界面选卡
POST /start →  选卡界面开始
```

坐标：**行 0..4（池塘/浓雾为 0..5），列 0..8，全部 0 基；行 0 是最上面一行，列 0 是最左边一列。**

- 屋顶：**5 行**（`0..4`），且只有有花盆（type 33）的格子能种；
- 池塘/浓雾：**6 行**（`0..5`），第 2、3 行是水面。

像素换算（`/click`、`/debug_click` 用，格子左上角）：

```text
白天/夜晚：x = 40 + col*80    y = 80 + row*100
池塘/浓雾：x = 40 + col*80    y = 80 + row*85
屋顶：     x = 40 + col*80    y = 70 + row*85 + (col<5 ? (5-col)*20 : 0)
```

点中心再加 `x+40`、`y+半格`（半格约 50/42）。

---

## 1. 启动桥

```bash
# 需要 Python 3.9+ 和 pvztools（见 README.md / requirements.txt）
python pvz_server.py 15580
```

先用 `GET /health` 确认 `{"ok": true, ...}`，再 `GET /state`。

如果 `/state` 一直 500：游戏没开，或游戏版本不是 1.0.0.1051。

---

## 2. 主循环（伪代码）

```
loop forever:
    s = GET /state

    if s.ui == "选卡界面":
        POST /pick  {"seeds": [...你的卡组...]}
        POST /start {"wait": 20}
        continue

    if not s.in_level:
        break                      # 通关/失败，交给外部处理

    free_cells = 所有格子
                 - 已有植物
                 - s.blocked        # 墓碑/弹坑/梯子/罐子
                 - s.ice            # 雪橇车冰面
                 - 无花盆的屋顶格（s.scene == 4 时需要 s.pots）
                 - 无荷叶的水面格（s.is_pool 时需要 s.lily）

    if s.conveyor:
        # 传送带：卡片按带上现有物品来，没有阳光经济
        pick a card from s.belt
        POST /plant
    else:
        # 普通关：按阳光经济选卡
        pick s.seeds 里 usable == true 且 cost <= sun
        POST /plant

    处理 409：看 reason 决定换卡/换格子/等待（见第 4 节）

    sleep 1~2 秒
```

---

## 3. `/state` 关键字段

```json
{
  "ok": true, "pid": 12345, "version": "1_0_0_1051_en",
  "in_level": true, "ui": "关卡中", "paused": false,
  "sun": 175, "wave": 8,
  "scene": 0, "is_pool": false, "conveyor": false,

  "seeds": [{"slot":0,"type":0,"name":"豌豆射手","cost":100,
             "game_usable":true,"cooldown_left_ms":0,
             "affordable":true,"usable":true}],

  "plants": [{"row":0,"col":1,"type":1,"name":"向日葵","hp":300,"index":3}],
  "zombies":[{"row":2,"x":412.5,"type":0,"name":"普通僵尸",
              "hp":270,"helmet_hp":0,"status":0,"altitude":0.0,
              "flying":false,"has_object":false,"in_pool":false}],
  "coins":  [...],
  "grid_items": [{"row":3,"col":6,"type":1,"name":"墓碑","blocking":true}],
  "blocked": [[3,6],[4,7]],
  "ice": [], "ice_rows": [],
  "water": [], "lily": [], "pots": [],
  "vases": [],
  "belt": [], "belt_ready": []
}
```

**可用性判断**：普通关看 `seeds[i].usable`；传送带关看 `belt`（`seeds[i].usable` 只表示"带上有"）。

- `version`：**pvztools 的 profile id**（`1_0_0_1051_en`），不是游戏内字段，别用它判断版本；
- `pid`：游戏进程 id（桥重挂后会变）

**场景码 `scene`**：`0` 白天 / `1` 夜晚 / `2` 池塘 / `3` 浓雾 / `4` 屋顶。
池塘和浓雾：第 2、3 行是水（6 行棋盘）。

---

## 4. `/plant` 的 409 reason 与应对

| reason | 含义 | 你应该做什么 |
| --- | --- | --- |
| `cooldown` | 这张卡冷却中（`cooldown_left_ms`） | 换一张卡，或等 |
| `no_sun` | 阳光不够（`cost` > `sun`） | 等阳光，或先种产阳光植物 |
| `card_not_usable` | 游戏层面这张卡不可用 | 换卡 |
| `occupied` | 格子已有植物（`plant` 字段说是谁） | 换格子 |
| `blocked` | 墓碑/弹坑/梯子/罐子（`item` 字段） | 换格子 |
| `ice` | 雪橇车冰面 | 换格子（冰约 30 秒化） |
| `needs_lilypad` | 水面没荷叶就种陆生植物 | 先种荷叶，或换格子 |
| `needs_flowerpot` | 屋顶没花盆就种植物 | 先种花盆，或换格子 |
| `water_only` | 水生植物被种到陆地 | 换到水面格子 |
| `buster_needs_grave` | 墓碑吞噬者只能种墓碑上 | 找 `grid_items` 里 `type==1` 的格子 |
| `not_on_belt` | 传送带关：带上没这张卡 | 从 `belt` 里挑现有的 |
| `not_foreground` | （旧版）需要前台 | 新版不会出现 |

**规则**：收到 409 不要原样重试；按 reason 换策略。

---

## 5. 特殊场景

### 5.1 传送带关（`conveyor: true`）

- `seeds[].cost` 全是 0，`usable` 只表示带上有没有
- 从 `belt` 挑卡：`belt: [{"slot":0,"type":14,"name":"寒冰菇"}]`
- 用掉一张 → 该格空出来 → **约 10 秒后游戏补新卡**；所以每次循环重新读 `/state`，不要缓存 `belt`
- `belt_ready` 是带上植物名字的集合，方便快速判断

### 5.2 池塘/浓雾（`is_pool: true`）

- 6 行（`0..5`），水面格子 = `water`（第 2、3 行）
- 水面上种陆生植物 → 必须先有荷叶（`lily`）
- 荷叶/缠绕水草/海蘑菇/香蒲只能种水里
- 荷叶（type 16）游戏内叫「睡莲」，pvztools 里叫「荷叶」，桥两者都认

### 5.3 屋顶（`scene: 4`）

- **5 行（`0..4`）**，只有 `pots` 里的格子能种普通植物
- 花盆本身在 `plants` 里，类型是 `33`，选格时要排除它
- 花盆是逐格检测的，会被砸掉，每次重读

### 5.4 打罐子关（`vases` 非空）

- 罐子内容可读：`vases: [{"row":3,"col":6,"vase_kind":"zombie","zombie":"铁桶僵尸"}]`
- 罐子算作 `blocked` 格子
- **敲罐子**：`POST /break_vase {"row":3,"col":6}`
- **种罐子里的植物**：打碎后地上会出现卡片，用 `POST /vase_plant {"row":4,"col":0}` 种到指定格
  （可选 `"type": 5` 指定拿哪张卡；不传就取第一张）
- 罐子内容可提前看 → 可以规划"先敲哪个"

### 5.5 空中僵尸

`zombies[i].flying == true` 表示在空中（气球僵尸）。
普通豌豆打不到，需要仙人掌/三叶草/香蒲等对空植物。

---

## 6. 经济规则

- 普通关：`/plant` **真的扣阳光**，并且**把冷却写回游戏**（卡片会变灰倒计时）
- 阳光成本/冷却时间由桥内部表决定（标准 1.0.0.1051 数值）
- 传送带关：不扣阳光、不进冷却，只消耗带上的卡

---

## 7. 最小可运行示例（Python）

```python
import json, time, urllib.request

B = "http://127.0.0.1:15580"

def get(p):
    with urllib.request.urlopen(B + p, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))

def post(p, body):
    req = urllib.request.Request(
        B + p, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))

def free_cells(s):
    occ = {(p["row"], p["col"]) for p in s["plants"]}
    occ |= {(r, c) for r, c in s.get("blocked", [])}
    occ |= {(r, c) for r, c in s.get("ice", [])}
    rows = 6 if s.get("is_pool") else 5
    cells = [(r, c) for c in range(9) for r in range(rows) if (r, c) not in occ]
    if s.get("is_pool"):
        pots_or_water = {(r, c) for r, c in s.get("lily", [])}
        cells = [cell for cell in cells
                 if cell not in s["water"] or cell in pots_or_water]
    if s.get("scene") == 4:
        pots = {(r, c) for r, c in s.get("pots", [])}
        cells = [cell for cell in cells if cell in pots]
    return cells

while True:
    s = get("/state")
    if s["ui"] == "选卡界面":
        post("/pick", {"seeds": ["小喷菇", "向日葵", "豌豆射手", "坚果"]})
        post("/start", {"wait": 20})
        continue
    if not s["in_level"]:
        break
    cells = free_cells(s)
    if s["conveyor"] and s["belt"] and cells:
        card = s["belt"][0]
        post("/plant", {"row": cells[0][0], "col": cells[0][1], "plant": card["name"]})
    elif cells:
        card = next((x for x in s["seeds"] if x["usable"]), None)
        if card:
            post("/plant", {"row": cells[0][0], "col": cells[0][1], "plant": card["name"]})
    time.sleep(1.5)
```

---

## 8. 硬约束（不要违反）

1. **不要**同时跑两个桥（pvztools 进程锁会冲突）
2. **不要**在同一个进程里既跑桥又跑别的 pvztools 用法
3. 游戏版本必须是 **1.0.0.1051**（内存偏移针对这版）
4. 游戏崩溃后重启，桥会按 pid 自动重挂，但**正在进行的关卡状态会丢**
5. 桥只支持 Windows（用了 `ctypes` + Win32 API）

---

## 9. 出问题怎么查

| 现象 | 检查 |
| --- | --- |
| `/state` 500 | 游戏进程在不在？版本对不对？ |
| `/plant` 一直 `cooldown` | 桥重启会清空本地冷却表，可能偏保守 |
| 卡片一直不可用 + `paused: true` | 游戏失焦会暂停，冷却不推进 |
| 传送带 `/plant` 404 | 从 `belt` 里挑，别写死卡名 |
| 种植返回 409 但植物出现了 | 已修复的旧 bug；若复现请读 `raw_plants_at` 逻辑 |

---

## 10. 小游戏模式（v2026-11-12 新增）

> 判断当前是哪种模式：`/state` 里没有直接的 `game_mode` 字段，
> 可用特征字段间接判断（`vases` 非空 = 破罐者，`belt` 非空 = 传送带类，`challenge.score` 变化 = 宝石迷阵系）。

### 10.1 宝石迷阵（Beghouled, mode 20）

- 5×8 网格，plant 就是"宝石"，靠交换相邻两格凑三连
- `POST /begh_swap {"row1":2,"col1":3,"row2":2,"col2":4}`
- ⚠️ 该接口仍用投递消息，全屏模式下可能失效

### 10.2 宝石迷阵 Twist（mode 24）

- 操作是**顺时针旋转 2×2 四格**：左上→右上→右下→左下→左上
- `POST /twist_rotate {"row":2,"col":3}`（row/col 是该 2×2 的**左上角**）
- 无效旋转（消不掉三连）游戏会自动转回去 → 调用后读 `/state` 确认真的变了
- 求解思路：对每个 2×2 模拟顺时针旋转，只挑"旋转后四个格子参与新三连"的块；
  连续两次无效就把该块拉黑换地方（避免死循环）
- 通关目标：`challenge.score` 达到 75

### 10.3 破罐者（Vasebreaker, mode 51）

- `vases[]` 提前给出每个罐子的内容（`vase_kind` = plant/zombie，附名字）
- 敲罐：`POST /break_vase {"row":R,"col":C}`
- 种罐子植物：`POST /vase_plant {"row":R,"col":C,"type":可选}`
  - 内部流程：点地上卡片（`Board::MouseDown`）→ 点目标格
  - 两步都必须用 `Board::MouseDown`，投递点击只能"收卡"、种不下去

### 10.4 谁笑到最后（Last Stand, mode 31）

- 清完一波后点屏幕底部中间的「继续猛攻」提前拉下一波（拿额外阳光奖励）
- `POST /next_wave`（内部点 `(400,570)`）

### 10.5 老虎机（mode 18）

- `POST /spin` 远程点拉杆
- 奖品是弹出卡片：`/state.coins` 里 `type==16 && seed_type>=0`，用 `POST /plant_prize {"row":R,"col":C}` 种下
- 三张卷轴图案只是动画，真正的奖品是那个 coin

### 10.6 雨关（It's Raining Seeds, mode 19）

- 卡片从天上掉，`/state.coins` 里能读到；`POST /plant_prize` 种下
- 水生植物只能种水里（桥会校验 `water_only`）

### 10.7 传送带（坚果保龄球等）

- `/plant` 自动走"点卡 → 点格子"的 UI 路径，种下瞬间补位
- 保龄球类关卡：球会滚出去，撞到僵尸后斜向弹开（属正常行为）
- 只能放前几列由关卡规则决定，放错桥会返回 409

### 10.8 我是僵尸（I, Zombie）

- 阳光是"脑子币"，卡槽里是僵尸卡（type 60/63/67 …）
- 放僵尸：`POST /click` 点卡（第 i 张中心 `(117+60*i, 42)`）→ 再点目标格；`/debug_click` 是同一套底层点击的调试别名，正常流程优先用 `/click`
- 目标：吃光最左列 `grid_items` 里 `type==12` 的脑子
- 已验证可放置（普通僵尸花 50）
