# API 参考

所有接口都是 `http://127.0.0.1:<port>`（默认 15580），返回 JSON。

坐标：**行 0..4（池塘/浓雾 0..5），列 0..8，0 基。**

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
- 选卡/开始：**投递窗口消息**（`WM_MOUSEMOVE` + 按下/松开），不需要窗口在前台
- 经济：远程调用不扣阳光/不进冷却，桥自己扣并把冷却写回游戏内存，使卡片 UI 正常变灰
