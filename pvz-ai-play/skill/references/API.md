# API 参考

所有接口都是 `http://127.0.0.1:<port>`（默认 15580），返回 JSON。

坐标：**行 0..4（池塘/浓雾 0..5），列 0..8，0 基。**
行 0 是最上面一行，列 0 是最左边一列；屋顶 5 行（0..4），池塘/浓雾 6 行（0..5，第 2、3 行水面）。

像素换算（`/click`、`/debug_click` 用，格子左上角）：

```text
白天/夜晚：x = 40 + col*80    y = 80 + row*100
池塘/浓雾：x = 40 + col*80    y = 80 + row*85
屋顶：     x = 40 + col*80    y = 70 + row*85 + (col<5 ? (5-col)*20 : 0)
```

点中心再加 `x+40`、`y+半格`。

---

## GET /health

```json
{"ok": true, "service": "pvz-bridge", "port": 15580}
```

## GET /state

返回完整棋盘状态。主要字段：

### 顶层

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ok` | bool | 是否成功 |
| `pid` | int | 游戏进程 id（桥重挂后会变） |
| `version` | str | **pvztools 的 profile id**（如 `1_0_0_1051_en`），不是游戏字段 |
| `ui` | str | `主菜单` / `选卡界面` / `关卡中` / `通关结算` / `未知(...)` |
| `in_level` | bool | 是否在关卡内（选卡界面也算 true） |
| `paused` | bool | 游戏是否暂停（失焦会暂停） |
| `sun` | int | 阳光 |
| `wave` | int | 当前波次 |
| `scene` | int | `0`白天 `1`夜晚 `2`池塘 `3`浓雾 `4`屋顶 |
| `is_pool` | bool | 是否池塘/浓雾（有水面） |
| `conveyor` | bool | 是否传送带关 |
| `chooser_picked` | int/null | 选卡界面已选数量 |

### `seeds[]`

| 字段 | 说明 |
| --- | --- |
| `slot` | 卡槽位置 0..n |
| `type` | 植物类型 id |
| `name` | 中文名 |
| `cost` | 阳光成本（传送带关恒为 0） |
| `game_usable` | 游戏层面是否可用 |
| `cooldown_left_ms` | 桥记录的剩余冷却 |
| `affordable` | 阳光是否够 |
| `usable` | **综合可用性**（普通关看这个） |
| `on_belt` | 传送带关：带上是否有这张 |

### `plants[]`

`row` `col` `type` `name` `hp` `index`

花盆(33)、荷叶(16) 会和上面的植物**同格共存**。

### `zombies[]`

| 字段 | 说明 |
| --- | --- |
| `row` `x` | 位置（x 是像素坐标） |
| `type` `name` | 类型 |
| `hp` `max_hp` `helmet_hp` `shield_hp` | 血量 |
| `status` | 内部状态（气球=73，走路=1） |
| `altitude` | 高度（气球僵尸飞在空中时 25） |
| `flying` | 是否在空中（altitude > 5） |
| `has_object` | 是否挂着东西 |
| `in_pool` | 是否在水里 |
| `mind_controlled` | 是否被魅惑 |
| `target_row/col` | 目标格（-1 表示无） |

### `grid_items[]` / `blocked`

场地物品：墓碑(1)、弹坑(2)、梯子(3)、传送门(4/5)、罐子(7)、蜗牛(10)、钉耙(11)、脑子(12)。

`blocked` 是不能种植物（也不能种墓碑吞噬者以外）的格子列表。

罐子额外字段：`vase_kind`（plant/zombie）、`plant`、`zombie`、`vase_tag`。

### `ice` / `ice_rows`

雪橇车冰面。`ice` 是不能种的格子；`ice_rows` 是原始数据（`timer > 0` 表示该行有冰）。

### `water` / `lily` / `pots`

- `water`：水面格子（池塘/浓雾）
- `lily`：有荷叶的格子
- `pots`：有花盆的格子（屋顶）

### `belt` / `belt_ready`

传送带关卡带上现有卡：`belt: [{slot, type, name}]`，`belt_ready` 是名字集合。

### `vases`

```json
[{"row":3,"col":6,"vase_kind":"zombie","zombie":"铁桶僵尸","vase_tag":2}]
```

---

## POST /plant

```json
{"row": 1, "col": 8, "plant": "向日葵", "wait": 10}
```

- `wait`（可选）：卡不可用时最多等多少秒

成功（200）：

```json
{"ok": true, "row":1, "col":8, "wanted":"向日葵", "placed":"向日葵",
 "charged":50, "sun_before":200, "sun":150, "cooldown_left_ms":7436, "index":12}
```

失败（409），`reason` 见下：

| reason | 说明 |
| --- | --- |
| `cooldown` | 冷却中 |
| `no_sun` | 阳光不够 |
| `card_not_usable` | 游戏层面不可用 |
| `occupied` | 格子已有植物（`plant` 字段） |
| `blocked` | 场地物品挡着（`item` 字段） |
| `ice` | 冰面 |
| `needs_lilypad` | 水面缺荷叶 |
| `needs_flowerpot` | 屋顶缺花盆 |
| `water_only` | 水生植物种到陆地 |
| `buster_needs_grave` | 墓碑吞噬者不在墓碑上 |
| `not_on_belt` | 传送带关：带上没这张卡（附 `belt`） |

植物不在卡槽 → `404 {"error": "卡槽里没有 'xxx'"}`

---

## POST /shovel

```json
{"row": 1, "col": 8}
→ {"ok": true, "removed": "向日葵"}
```

---

## POST /pick

选卡界面选卡。

```json
{"seeds": ["小喷菇","向日葵","豌豆射手","坚果","寒冰射手","樱桃炸弹"]}
→ {"ok": true, "picked":[...], "picked_count":6, "bank_size":6,
   "cleared_ok": true, "failed": []}
```

- 卡槽比传入多时**自动补满**（默认卡池）
- 每张卡点击后都会校验已选数量，失败会重试一次
- 不在选卡界面 → `409`

## POST /start

```json
{"wait": 20}
→ {"ok": true, "ui": 3}
```

点「Let's Rock!」并轮询界面切换。

## POST /continue（实验性，未校准）

结算界面/主菜单的点击推进。**坐标未校准，不建议依赖。**

---

## 实现方式备注（给维护者）

- 读状态：直接读进程内存（`ReadProcessMemory`），不依赖注入
- 种植/铲除：`pvztools` 的**远程调用**，在游戏进程内执行其自身函数
- 点击：**远程调用游戏自身的点击处理**
  - 棋盘内 → `Board::MouseDown(0x411F20)`，参数是**棋盘逻辑坐标**（与窗口/全屏无关）
  - 界面（选卡/按钮）→ `WidgetManager::MouseDown(0x539390)`，参数是**逻辑坐标**
  - 旧版用的"投递窗口消息"在**全屏模式下失效**，已降级为回退方案
- 经济：远程调用不扣阳光/不进冷却，桥自己扣并把冷却写回游戏内存，使卡片 UI 正常变灰

---

# v2026-11-12 新增接口

> 这一版把"点"从"投递窗口消息"改成了**直接调用游戏的点击处理函数**，
> 因此**窗口模式和全屏模式都能用**（旧版的全屏下投递点击无效）。

## 通用

### POST /debug_click

**调试接口，不写进主流程。** 远程调用 `Board::MouseDown(x, y, 1)`。棋盘逻辑坐标，`(0,0)` 是棋盘左上角。

```json
{"x": 480, "y": 290} → {"ok": true, "clicked": [480, 290]}
```

### POST /click

通用点击（低层接口），默认走 `Board::MouseDown`；传 `"method":"post"` 回退到投递消息。正常种植/铲除优先用 `/plant`、`/shovel`。

```json
{"x": 232, "y": 566}                  → 棋盘点击
{"x": 232, "y": 566, "method": "post"} → 投递点击（仅窗口模式可靠）
```

### POST /recalibrate

窗口/全屏切换后重新校准坐标映射（只影响回退用的投递点击）。

```json
→ {"ok": true, "calibrated": true}
```

### POST /force_plant

**调试接口，不写进主流程。** 强制在指定格放一株植物（**不检查卡槽/阳光/冷却**，跳过校验，用于调试与特殊关卡）。

```json
{"row": 0, "col": 6, "type": 33}   // 33 = 花盆
→ {"ok": true, ...}
```

---

## 传送带关卡

### POST /belt_compact

把带上空槽后面的卡整体前移，并按游戏规则设置滑动动画（左移 N 格 → `offset += 50*N`）。

```json
{"slots": 10}
→ {"ok": true, "moved": 2, "before": [34,-1,16,16], "after": [34,16,16,-1]}
```

> 正常 `/plant` 在传送带关会**自动补位**，一般不需要手动调用。

---

## 老虎机（game_mode 18）

### POST /spin

远程调用 `Board::MouseDown` 点拉杆（`(510,40)`），并等待转盘启动。

```json
{"wait": 1.0} → {"ok": true, ...}
```

---

## 宝石迷阵（game_mode 20）

### POST /begh_swap

```json
{"row1": 2, "col1": 3, "row2": 2, "col2": 4}
→ {"ok": true, ...}
```

> 实现：写 `challenge+8=1`、选中坐标，再投递 `WM_MOUSEMOVE` 到目标格。
> ⚠️ 这是**目前唯一仍依赖投递消息**的接口，全屏模式下可能失效（待替换）。

---

## 宝石迷阵 Twist（game_mode 24）

### POST /twist_rotate

顺时针旋转以 `(row,col)` 为**左上角**的 2×2 四格。
内部调用 `0x420280(challenge, x, y)`，点击锚点是该块的**右上角**。

```json
{"row": 2, "col": 3, "wait": 0.7}
→ {"ok": true, "row":2, "col":3, "game_mode":24, "click":[311,320],
   "sun_before":75, "sun":100, "sun_gain":25}
```

> 无效旋转（消不掉三连）游戏会自己转回去，所以调用后要读 `/state` 确认。

---

## 破罐者（game_mode 51）

### POST /break_vase

```json
{"row": 3, "col": 6}
→ {"ok": true, "content": "plant", "detail": "豌豆射手", "click": [560, 390]}
```

罐子内容可提前从 `/state.vases` 读取。

### POST /vase_plant

把地上掉的植物卡片种到指定格（**点卡片 + 点格子，两步都用 `Board::MouseDown`**）。

```json
{"row": 4, "col": 0}                 // 种卡片池里第一张
{"row": 4, "col": 0, "type": 5}      // 指定植物类型（5=寒冰射手）
→ {"ok": true, "type":5, "name":"寒冰射手",
   "card_click":[380,180], "cell_click":[80,490],
   "planted": {"row":4,"col":0,"type":5,"hp":300}}
```

---

## 谁笑到最后（Last Stand, game_mode 31）

### POST /next_wave

点屏幕底部中间的「继续猛攻」按钮（逻辑坐标 `(400,570)`）。

```json
→ {"ok": true, "zombies_before":0, "zombies_after":5,
   "wave_after":1, "clicked":[400,570]}
```

---

## 雨关 / 老虎机奖品

### POST /plant_prize

把场上"植物卡片"（`coins[]` 里 `type==16` 且 `seed_type>=0` 的对象）种到指定格。

```json
{"row": 1, "col": 3, "type": 5}
→ {"ok": true, ...}
```

---

## `/state` 新增字段（v2026-11-12）

| 字段 | 说明 |
| --- | --- |
| `challenge{state,counter,score,sel_flag,sel_x,sel_y}` | 小游戏状态机（Twist 的分数在 `score`） |
| `coins[]` | 可拾取物：`type/x/y/collecting/seed_type/seed_name` |
| `grid_items[].vase_kind` | 罐子内容：`plant`/`zombie` |
| `belt_ready[]` | 传送带上植物名字集合 |
