# PvZ1 桥（状态 + 动作）

- 版本：0.2.0（全屏兼容 + 小游戏接口）
- 日期：2026-11-12
- 作者：续灯（AI 助手）；发布：dhd
- 目标游戏：Plants vs. Zombies 1.0.0.1051（英文零售版，用户自备）
- 服务端：`pvz_server.py`，默认 `http://127.0.0.1:15580`
- 依赖：`pvztools >= 0.2.0`（`pip install pvztools`，或用 `PVZTOOLS_VENDOR` 指向离线目录）

---

## 一、启动

```powershell
python pvz_server.py 15580
```

启动后先 `GET /health` 确认。

## 二、接口

### GET /health

```json
{"ok": true, "service": "pvz-bridge", "port": 15580}
```

### GET /state

```json
{
  "ok": true, "pid": 27744, "version": "1_0_0_1051_en",
  "in_level": true, "ui": "关卡中",
  "sun": 175, "wave": 8, "paused": false,
  "seeds": [{"slot": 0, "type": 0, "name": "豌豆射手", "usable": true,
             "cd_elapsed": 0, "cd_total": 750}],
  "plants": [{"row": 0, "col": 1, "type": 1, "name": "向日葵", "hp": 300, "index": 3}],
  "zombies": [{"row": 2, "x": 412.5, "type": 0, "name": "普通僵尸",
               "hp": 270, "helmet_hp": 0}],
  "coins": [{"type": 4, "x": 46.0, "y": 33.0, "collecting": false}]
}
```

**坐标约定：行 `0..4`、列 `0..8`，全部 0 基**（pvztools 内部是 1 基，桥已换算）。

### POST /plant

```json
{"row": 1, "col": 8, "plant": "向日葵", "wait": 10}
```

- `plant`：中文名 / 英文名 / 类型 id 都行
- `wait`：可选，最多等这么多秒直到卡可用（冷却完 + 阳光够）
- 成功：`{"ok":true,"placed":"向日葵","index":25,...}`
- 卡不可用：`409 {"ok":false,"reason":"card_not_usable","seed":{...}}`
- 种下去但类型不符：`409 {"ok":false,"placed":"豌豆射手","wanted":"向日葵"}`

### POST /shovel

```json
{"row": 1, "col": 8}
```
- 成功：`{"ok":true,"removed":"向日葵","left":[]}`
- 该格没植物：`404 {"ok":false,"error":"该格没有植物"}`

## 三·补 传送带关卡（特殊关卡）

传送带关卡没有阳光经济、没有冷却，卡片在带子上排队送过来。桥的做法：

- **判定**：读 `seed_bank.conveyor_belt_counter`（`bank + 0x34C`），非 0 即传送带关。
  （pvztools 的 `classify()` 会把它误判成普通冒险关，所以不用它的结论。）
- **`/state`** 多两个字段：
  ```json
  {"conveyor": true,
   "belt": [{"slot": 0, "type": 2, "name": "樱桃炸弹"}, {"slot": 3, "type": 0, "name": "豌豆射手"}]}
  ```
- **`/plant`** 在传送带上走另一条分支：
  1. 在带上找同类型的一张卡；
  2. `Board::AddPlant` 放置；
  3. **把该槽 `type` 写 -1**（游戏自己的消耗方式）；
  4. **不扣阳光、不记冷却**。
- 请求的植物不在带上 → `404 {"reason":"not_on_belt","belt":[...]}`。

实测（2026-11-07）：

```text
用「豌豆射手」种到 (4,4)
200 {"ok":true,"conveyor":true,"placed":"豌豆射手","from_belt_slot":3,"belt_left":9}
```

注意：传送带上同样的植物可能有多张，桥取**最左边那张**（slot 最小的）。

## 三·补二 选卡界面（真实鼠标）

选卡界面只认**真实硬件鼠标**（投递 `WM_LBUTTONDOWN` 无效）。桥里用
`SetCursorPos` + `mouse_event` 真点，流程已验证可用。

```json
POST /pick  {"seeds": ["小喷菇","向日葵","豌豆射手","坚果","寒冰射手","双发射手"]}
→ 200 {"ok": true, "picked": [...], "bank_size": 6}

POST /start {"wait": 12}
→ 200 {"ok": true, "ui": 3}
```

流程：**点卡槽第 0 格 N 次清空 → 逐张点选 → 点 Let's Rock → 轮询 `ui==3`**。

坐标来自 pvztools：`chooser_card_xy(id)`、`bank_packet_xy(0, size)`、`LETS_ROCK_XY=(232,566)`。

### 坑：夜晚关必须带小喷菇

实测 2-1（level 11）不带小喷菇会弹「You must select a puff-shroom」警告框，
点 Let's Rock 只会弹框、不进关（`ui` 一直是 2）。**带小喷菇后一次成功**（约 5 秒后 `ui` 变 3）。

建议：`/pick` 的卡组里常备小喷菇，或按关卡 scene 判断夜晚关。

## 三·补三 墓碑 / 弹坑 / 梯子（场地物品）

夜晚关有墓碑，**那格不能种**。`/state` 现在直接给出：

```json
"grid_items": [
  {"row":3,"col":6,"type":1,"name":"墓碑","blocking":true},
  {"row":4,"col":7,"type":1,"name":"墓碑","blocking":true}
],
"blocked": [[3,6],[4,7],[2,8],[3,8]]
```

- `blocking=true` 的（墓碑=1 / 弹坑=2 / 梯子=3）不能种；钉耙(11)不影响。
- `/plant` 现在会**先校验**：
  - 格子有植物 → `409 {"reason":"occupied","plant":"向日葵"}`
  - 格子被墓碑等占着 → `409 {"reason":"blocked","item":"墓碑"}`
- 数据来源：`Board.mGridItems`（`board+0x11C`，步长 `0xEC`，`type +0x8 / col +0x10 / row +0x14 / dead +0x20`）。

**选格子时请用 `plants` + `blocked` 一起算空格，别只看 `plants`。**

## 三·补四 性能（已优化）

| 接口 | 优化前 | 优化后 |
| --- | --- | --- |
| `GET /state` | ~1665 ms | **15–20 ms** |
| `POST /plant` | ~1700 ms | **~110 ms** |

原因：早期每次请求都跑 `tasklist` 查进程（一次 ~1.5s）。现在 pid 缓存 3 秒。

另外「扣阳光 + 写冷却」已提到种植调用之后**立刻执行**，不再等校验，
所以卡片变灰不会滞后。

`POST /pick` 约 8 秒（6 次真实点击，每次含悬停/按下/松开/间隔），属正常。

## 三·补五 结算 / 主菜单（实验性，未校准）

`POST /continue` 存在，但**坐标没校准**：这版游戏缺 pvztools 依赖的
`award_start_button` / `game_selector_clicked_adventure` 函数，只能靠点击找。

现状：`ui=5`（结算）时在底部区域扫候选点，命中即停并返回 `clicked:[x,y]`。
**结算界面目前需要用户手动点击**，不要依赖这个端点。

以后要自动化的话：打一关 → 调一次 `/continue` → 看返回的 `clicked` 坐标 →
把 `AWARD_CLICK_CANDIDATES` 换成那个固定点即可。

## 三·补六 选卡：现状与限制（2026-11-08）

**结论：选卡仍靠真实鼠标，但已改为「可校验 + 明确报错」。**

- 已找到 `SeedChooserScreen`（`*(app+0x774)`）和**已选数量**（`chooser+0xD24`，实测 0→3）。
- 已选卡不是普通整数数组，而是**每张卡一个控件**（选中时 x/y/状态位变化），
  没有现成的「数组写几下就行」的入口。
- 试过远程调用 UI 函数 `choose_card`(0x486030) / `mouse_down`(0x539390)：
  **都会超时挂住**（游戏不死，但调用不返回）——UI 函数依赖消息循环上下文，不能在远程线程直接调。
- 所以 `/pick` 保留真实鼠标，但加了：
  1. **前台检查**：`GetForegroundWindow() != 游戏窗口` → `409 not_foreground`，不再盲点；
  2. **逐张校验**：点一张读一次 `chooser+0xD24`，数量没涨就重试一次；
  3. **每次重校准**：窗口移动/缩放后坐标仍然准（本来就是 client→screen 实时换算）。

真实鼠标的硬限制：**游戏窗口必须在前台**。后台/无焦点时点击不会送达。

## 三·补七 选卡改用「投递消息」——不需要前台了

**重大修正**：早期结论「投递 `WM_LBUTTONDOWN` 无效」**是错的**。
当时用 `bank_types()` 验证，而选卡界面的种子槽要开局才填，所以永远读到空，误判了。

用真实的「已选数量」（`chooser+0xD24`）验证后确认：**投递消息完全有效**，
只要先发 `WM_MOUSEMOVE` 再发按下/松开。

现在的 `/pick` 和 `/start`：

| 项 | 之前（真实鼠标） | 现在（投递消息） |
| --- | --- | --- |
| 需要窗口前台 | **是**（否则点击丢弃） | **否** |
| 占用光标 | 是 | 否 |
| 窗口移动/缩放敏感 | 缩放敏感 | 每次重新校准，稳 |
| 耗时 | 15 秒 / 20 秒 | **3.6 秒 / 5.4 秒** |
| 失败可见性 | 盲点 | 每张卡读一次计数，失败重试 |

实测（2026-11-08，窗口无焦点状态）：

```text
/pick  → ok=true, picked=6张, picked_count=6, cleared_ok=true   (3.6s)
/start → ok=true, ui=3                                          (5.4s)
```

## 三·补八 阳光菇瞬间长大（已修）

**现象**：`/plant` 种的阳光菇一放下就是大形态（原版小形态要维持 2 分钟）。

**根因**：`Board::AddPlant`（远程调用）把 `state_countdown` 初始化成 **1**（应为 **12000**，即 120 秒），
游戏下一帧就判定"已长大"，动画也按大形态建好。

**关键点（踩过坑）**：种完**再**改字段没用——会出现
「逻辑是小形态（产 15 阳光）、模型是大形态、动画停止」的鬼样子。
必须**在同一次远程调用内**写完：

```asm
push -1            ; imitater type
push 9             ; 阳光菇
mov eax, row
push col
mov ebp, board
push ebp
call Board::AddPlant      ; EAX = 新植物指针
mov dword [eax+0x54], 12000 ; state_countdown（120 秒，原版值）
mov dword [eax+0x3C], 23   ; 小形态
```

实现见 `plant_remote()`。其它植物仍走普通远程调用。

## 三·补九 植物功能验证（2026-11-08）

远程调用种植后逐种实测：

| 植物 | 结论 | 观察到的状态 |
| --- | --- | --- |
| 土豆雷 | ✅ 正常 | `state=0` 武装中（cd~1500）→ `state=16` 已武装 |
| 樱桃炸弹 | ✅ 正常 | 种下约 1 秒后爆炸消失，附近僵尸 2→1、总血 540→270 |
| 墓碑吞噬者 | ✅ 正常 | 必须种在墓碑上（桥已放行 `type=11` 对 `type=1` 的拦截）；`state=9`，墓碑被清除 |
| 大嘴花 | ✅ 正常 | `state=1` 待命 → 吃到僵尸后 `state=13`、`cd≈3600` 咀嚼 |
| 阳光菇 | ✅ 需补初始化 | 见「三·补八」，小形态 120 秒 |

**放行规则**：`/plant` 遇墓碑默认 `409 blocked`，
但种「墓碑吞噬者」时放行（它本来就要种在墓碑上）。

## 三·补十一 传送带：消耗方式修正（重要，2026-11-08）

**正确行为**：用掉一张卡 → **只把该格清空**（`type=-1`）→ 游戏过约 10 秒在空位补一张新卡。

**不要手动"左移补位"**：实测游戏自己不会让后面的卡往前挤。
早期实现搬了 `type/坐标/冷却` 过去，结果把腰带数据搞坏：
`index` 全变成 9、`usable` 全变 0 → 卡片灰掉、"重新装填中"、还占着位置。

`consume_belt_packet()` 现在只做：

```text
type = -1, imitater = -1, offset_x = 0, cd_elapsed = 0, cd_total = 0,
usable = 1, refreshing = 0
```

实测：种掉第 0 张后 `[空,13,14,...]`，+4 秒变 `[12,13,14,...]`，
+8 秒继续正常流动。

## 三·补十 传送带关卡：卡片可用性修正（用户反馈）

**现象**：在传送带关什么都不做。

**原因**：`/state` 仍按「阳光成本 + 冷却」判定可用性，
而传送带关**没有阳光经济**，于是所有卡都 `affordable=False, usable=False` —— 使用者看到「没牌可打」。

**修正**（`conveyor=true` 时）：

```json
"seeds": [{"slot":0,"type":14,"name":"寒冰菇","cost":0,
           "game_usable":true,"affordable":true,"usable":true,"on_belt":true}],
"belt": [{"slot":0,"type":14,"name":"寒冰菇"}],
"belt_ready": ["寒冰菇","毁灭菇","魅惑菇","墓碑吞噬者"]
```

- 可用性 = **带子上有没有这张卡**，与阳光/冷却无关
- `cost` 一律 0，`usable` 仅在带上存在时为 true
- 新增 `belt_ready`：带上现有植物的名字集合，方便直接挑

另外传送带分支补了和普通分支一致的校验：

- 格子已有植物 → `409 occupied`
- 格子被墓碑等占着 → `409 blocked`（墓碑吞噬者除外）
- 墓碑吞噬者种在非墓碑格 → `409 buster_needs_grave`

实测：连续 4 次传送带种植（寒冰菇×2、毁灭菇、魅惑菇）全部 200，带子正常左移补货。

## 三·补十二 池塘关（Pool / Fog）种植限制

`board+0x554C` 是 `Board.mScene`：`0`白天 / `1`夜晚 / `2`池塘 / `3`浓雾 / `4`屋顶。

**池塘关是 6 行（0~5），第 2、3 行是水面**，其余是陆地。

`/state` 新增：

```json
"scene": 2,
"is_pool": true,
"water": [[2,0],[2,1],...,[3,8]],   // 水面格子（18 个）
"lily":  [[2,0]]                    // 已有荷叶的格子
```

`/plant` 规则（两种新拒绝理由）：

| 情况 | 结果 |
| --- | --- |
| 水面格子 + 陆生植物 + 没有荷叶 | `409 needs_lilypad` |
| 水面格子 + 陆生植物 + 有荷叶 | ✅ 可以种（荷叶在下面，植物在上面） |
| 水面格子 + 荷叶 | ✅ 可以种 |
| 陆地 + 水生植物（荷叶 16 / 缠绕水草 19 / 海蘑菇 24 / 香蒲 43） | `409 water_only` |
| 陆地 + 陆生植物 | ✅ 正常 |

同一格可以同时存在「荷叶 + 一株其它植物」；桥的占位判断会把荷叶排除在外。

**名字别名**：pvztools 把这株叫「荷叶」，玩家常说「睡莲」，桥两者都认
（见 `PLANT_ALIASES`）。

实测（2026-11-08）：水面种向日葵 → `needs_lilypad`；水面种荷叶 → ok；
荷叶上种向日葵 → ok（板上出现 `荷叶 + 向日葵`）；陆地种荷叶 → `water_only`。

## 三·补十三 雪橇车冰面（不能种）

雪橇车（冰车僵尸）开过会留冰面，冰面上**不能种植物**。

Board 里按行存两个数组（stride 4，长度 6）：

```text
board + 0x60C  冰面左边界 x（像素，默认 800 = 无冰；雪橇车开过时向左推进）
board + 0x624  冰面剩余时间（>0 表示这一行有冰，约 3000 = 30 秒）
```

一格被冰覆盖 = 该行 `timer > 0` 且 格子右边界 `40 + 80*(col+1) > min_x`。

`/state` 新增：

```json
"ice": [[1,7],[1,8]],
"ice_rows": [{"row":0,"min_x":800,"timer":0},
             {"row":1,"min_x":661,"timer":2999}, ...]
```

`/plant` 落在冰面格子 → `409 {"reason":"ice"}`。

实测（2026-11-08）：召唤冰车开过第 1 行 → `min_x=661, timer=2999`，
`ice=[[1,7],[1,8]]`，向 (1,7) 种植返回 `409 ice`。

## 三·补十四 僵尸字段扩展（气球僵尸等）

`/state` 的 `zombies[]` 现在带完整状态字段：

```json
{"row":2,"x":478.8,"type":16,"name":"气球僵尸",
 "hp":270,"max_hp":270,"helmet_hp":0,"shield_hp":0,
 "status":73,"altitude":25.0,"flying":true,
 "has_object":false,"in_pool":false,"speed":0.344,
 "mind_controlled":false,"target_row":-1,"target_col":-1}
```

**气球僵尸**（type 16）关键点：

- 飞在空中时 `altitude = 25`、`status = 73`、`flying = true`
- 气球被打掉后 `altitude` 归零、`flying` 变 false，开始正常走路
- 地上僵尸 `altitude = 0`、`flying = false`

其它字段用途：

| 字段 | 说明 |
| --- | --- |
| `status` | 僵尸内部状态（气球=73，路障走路=1） |
| `has_object` | 是否挂着东西（梯子、报纸等） |
| `in_pool` | 是否在水里 |
| `speed` | 当前速度 |
| `mind_controlled` | 被魅惑菇控制 |
| `target_row/col` | 目标格子（-1 表示没有） |

实测（2026-11-08）：召唤气球僵尸 → `altitude=25, status=73`，
x 从 478 一路推进到 205。

## 三·补十五 打罐子关（Vasebreaker）：罐子内容可读

罐子是网格物品 **type = 7**，内容存在额外字段里：

```text
grid_item + 0x3C  僵尸类型（-1 = 不是僵尸罐）
grid_item + 0x40  植物类型（-1 = 不是植物罐）
grid_item + 0x44  罐子种类（1 = 植物罐，2 = 僵尸罐）
```

`/state` 新增 `vases`：

```json
"vases": [
  {"row":2,"col":8,"vase_kind":"plant","plant":"豌豆射手","vase_tag":1},
  {"row":3,"col":6,"vase_kind":"zombie","zombie":"铁桶僵尸","vase_tag":2}
]
```

`grid_items[]` 里也会带上同样的 `vase_kind / plant / zombie / vase_tag` 字段。
罐子会算作 **阻挡格**（`blocked` 里包含），不能往上种。

网格物品类型全表（pvztools `GRID_ITEM_TYPES`）：

```text
1 墓碑  2 弹坑  3 梯子  4/5 传送门  7 罐子  10 蜗牛  11 钉耙  12 脑子
```

实测（2026-11-08，打罐子关 16 个网格物品）：

```text
15 个罐子 + 1 个钉耙
5 个豌豆射手罐、5 个窝瓜罐、4 个普通僵尸罐、1 个铁桶僵尸罐
```

**注意**：pvztools 的 `classify()` 会把这个关误判成 CONVEYOR
（它按 adventure_level 5/35 猜的），不要信它的结论，直接看 `vases`/`grid_items`。

## 三·补十六 屋顶关（Roof）：必须踩花盆

`board+0x554C` 的场景码 `4` = 屋顶。

规则（**逐格检测**，不是固定列数——花盆可能被砸掉或玩家自己种）：

| 情况 | 结果 |
| --- | --- |
| 屋顶 + 格子有花盆(33) | ✅ 可以种其它植物（花盆在下面） |
| 屋顶 + 格子没有花盆 | `409 needs_flowerpot`（只有花盆本身能种） |
| 屋顶 + 已有花盆的格子再种花盆 | `409 occupied` |

`/state` 新增 `pots`：

```json
"pots": [[0,0],[0,1],...]   // 当前有花盆的格子
```

花盆和荷叶一样是「底座」：占位判断会把它们排除，
所以「花盆 + 豌豆射手」同格是合法状态。

### 顺手修的一个校验 bug

`/plant` 原来用 pvztools 的植物列表校验，**在底座上种植时会读不到新植物**
（列表滞后/过滤），导致明明种成功却返回 409。
现在改成**直读内存** `Board.mPlants`（`raw_plants_at()`），
判断"该格是否存在目标类型的植物"。

实测（2026-11-08，屋顶关）：

```text
有花盆 (0,3) 种豌豆射手 → 200 ok placed=豌豆射手 charged=100
无花盆 (3,6) 种豌豆射手 → 409 needs_flowerpot
```

## 三·补十七 老虎机拉杆（远程调用游戏函数，已验证）

老虎机（`game_mode == 18`，`CHALLENGE_SLOT_MACHINE`）的拉杆**不能靠写内存**：
直接写滚轮字段会让状态机不闭合，`main_counter` 冻结，最终
`Access Violation at 0x512961`（绘制函数）崩溃。

正确做法是**远程调用游戏自己的点击入口**：

```text
Board::MouseDown      @ 0x411F20   (this=ECX=board, 参数 x, y, clickCount, ret 0xC)
点击分发器             @ 0x421F10   (game_mode==18 且命中 ID==18 时执行拉杆)
把手矩形计算           @ 0x4221B0   rect = (seed_bank+8 + 0x1D9, seed_bank+0xC, 55, 80)
扣费                   @ 0x41BA60   Board::TakeSun(25)
```

实测（2026-11-12）：`seed_bank.pos=(10,0)` → 把手矩形 `(483,0,55,80)`，
中心 `(510,40)`；远程调 `Board::MouseDown(510,40,1)` 后
`sun 50→25`、`challenge_state 0→4`，滚轮正常转动并结算。

`/spin` 接口：

```json
POST /spin {"wait": 10}
→ {"ok": true, "saw_spin": true, "click": [510, 40],
   "sun_before": 150, "sun": 125, "cost": 25,
   "reels": [5, 3, 1], "reel_names": ["寒冰射手","坚果","向日葵"]}
```

- 只在 `game_mode==18` 生效，普通关卡返回 `409 not_slot_machine`
- 转轮状态 `challenge+0x54 != 0`（正在转）时返回 `409 spinning`
- 阳光不足返回 `409 no_sun`
- 连续 5 次实测全部成功，游戏无异常

**教训**：凡是"游戏自己有完整处理流程"的交互，优先远程调用它的入口函数；
直接改中间状态字段几乎一定会破坏状态机。

## 三·补十八 老虎机奖品：弹出卡片怎么种

老虎机赢到植物后，**不会**出现在那 3 个转轮格子里，而是以
**`type=16` 的"硬币"**形式从机器下方弹出（实测固定在 `(360, 85)` 附近），
其 `usable_seed_type` 就是奖品植物类型。

正确种植流程（游戏自己的逻辑）：

```text
1. 点卡片：Board::MouseDown @0x411F20  参数 (coin.x, coin.y, 1)
2. 点格子：Board::MouseDown @0x411F20  参数 (cell_x, cell_y, 1)
3. 游戏自己完成种植并消耗掉这张卡片（硬币消失）
```

`/state.coins[]` 现在带 `seed_type` / `seed_name`：

```json
"coins": [{"type":16, "x":360.0, "y":85.0, "seed_type":5, "seed_name":"寒冰射手"}]
```

`/plant_prize` 一步到位：

```json
POST /plant_prize {"row":0, "col":0}
→ {"ok":true, "prize_click":[360,85], "cell_click":[80,90],
   "type":3, "name":"坚果", "planted":{...}}
```

`type` 可选，用于在有多张奖品卡时指定要种哪一种。

**注意**：

- 老虎机模式下点那 3 个转轮格子，游戏只会把 `challenge+0x70` 钳到 2，
  **不会选卡**——别用 `/plant` 直接种（会绕过卡片、白嫖植物）。
- 奖品硬币是临时的，转完几秒内要种掉。
- 格子像素换算：`x = 80 + 80*col`，`y = 40 + step*row + step/2`，
  `step` = 100（日/夜/屋顶）或 85（池塘/浓雾）。

## 三·补十九 雨关（It's Raining Seeds, game_mode 19）

种子的表现形式和老虎机奖品一样：`type=16` 的硬币，`usable_seed_type` = 植物类型。
区别是**雨关的卡片会从天上掉下来**（y 不断增大），落地后才稳定。

`/state.coins[]` 能直接读到它们（`seed_name` / `x` / `y`）。

**注意**：雨关里远程点击（`Board::MouseDown` / `Coin::Collect`）**收不了卡**，
所以 `/plant_prize` 在本关走另一条路：

```text
1. AddPlant 把植物种到目标格
2. 把那张卡片标记为已销毁（coin+0x38 = 1，游戏自己收尾时也是这么做的）
```

实测：睡莲卡片 → (0,0) 种下 → 卡片 3→2 ✓

**坑**：`AddPlant` 不做地形校验，所以桥自己对水生植物做了检查
（池塘/浓雾场景里必须种在水面行，否则返回 `409 water_only`）。

## 三·补二十 宝石迷阵（Beghouled, game_mode 20）

- 棋盘 **5 行 × 8 列**，每格的"宝石"就是植物 type（豌豆/坚果/寒冰/小喷菇/杨桃/磁力菇…）
- 只有**能凑出 3 连及以上**的交换才会被接受（无效交换游戏直接拒绝）
- 格子像素：`x = 40 + (col+0.5) * 77.5`，`y = 80 + (row+0.5) * 96`

### 不用鼠标的交换方法（已验证 8/8）

游戏的处理流程是「记下选中格 → 鼠标移动时比较相邻格 → 交换」。所以我们：

```text
1. 写 challenge+8 = 1            （选中标志）
2. 写 challenge+0xC / +0x10      （A 格像素坐标，int）
3. 投递 WM_MOUSEMOVE(0x200) 到 B 格（PostMessage，真实光标不动）
4. 游戏更新循环自己完成交换、消除、下落
```

接口：

```json
POST /begh_swap {"a":[r1,c1], "b":[r2,c2], "wait":1.2}
→ {"ok":true, "pixel_a":[...], "pixel_b":[...], "sun_before":250, "sun":275, "sun_gain":25}
```

只在 `game_mode==20` 生效，否则返回 `409 not_beghouled`。

**注意**：连锁消除期间棋盘会短暂为空/不完整，算出来的"可行交换"可能为 0，
等 1~2 秒再算即可。

## 三·补二十一 传送带补位（已修复，2026-11-12）

### 现象
传送带关卡里，AI 种下一张卡后，**前面的卡不往前补位**；有时会看到
"后面新飞来的卡穿过前面的卡去填空位"。

### 机制（反汇编 + 现场快照还原）
- 每张卡的位置 = `packet+0x08`（槽位基础 X = 91 + 50*槽位）**+ `packet+0x30`**（offset，剩余滑动距离）
- 游戏每 4 帧把所有 `offset>0` 的卡减 1，减到 0 就停住（到位）
- 可点区域 ≈ `绘制X+19 .. 绘制X+59`，y 在 10~70
- 游戏自己补位时会**重设 offset**：左移 N 格 → `offset += 50*N`；
  飞行中的卡 index 减 N、offset 加 50*N（绝对位置不变，不会穿过别的卡）

### 修复（桥里已实现）
1. `/plant` 传送带分支改走**游戏 UI 路径**：点卡 `(base+offset+39, 40)` → 点格子，
   让游戏正常消费卡片
2. 种下瞬间立刻 `compact_belt()`：把空槽后面的卡整体前移，并按上面的规则设动画值

### 结果
连续实测：种 slot0 → 卡整体左移一格，画面正常滑动，不再出现"穿卡"。

## 三·补二十二 宝石迷阵 Twist（game_mode 24）

和宝石迷阵一样是 5×8 的 type 网格，但操作从"交换两格"变成**顺时针旋转 2×2 四格**：

```text
左上 -> 右上 -> 右下 -> 左下 -> 左上   （顺时针）
```

### 调用入口
`Challenge` 的点击分发器在 `mode==0x18(24)` 时调用 `0x420280(challenge, x, y)`：

```text
POST /twist_rotate {"row":R, "col":C, "wait":0.7}
R,C = 2x2 块的左上角
点击锚点 = 该块的「右上角」格 (R, C+1) 的中心像素
```

格心像素同宝石迷阵：`x = 40+(c+0.5)*77.5`，`y = 80+(r+0.5)*96`。

### 关键行为（踩坑记录）
- **无效旋转会自己转回去**（不消三连的旋转 = 无效果），所以判定"这次旋转是否有效"要看旋转后是否形成 3 连
- 点击锚点不是左上角也不是右下角，是**右上角**；锚点错会完全没反应
- 求解器：对每个 2×2 模拟顺时针旋转，只有"旋转后四个格子参与新的三连"才算有效
- 连续两次旋转无效就把该块拉黑，换别的块（避免死循环卡住）

### 实测
自动旋转约 3 分钟把 score 从 0 打到 **75 通关**（与宝石迷阵相同目标）。

## 三·补二十三 谁笑到最后（Last Stand, game_mode 31）「继续猛攻」

- 关卡里清完一波后，屏幕**底部中间**会出现「继续猛攻」按钮
- 逻辑坐标固定：**(400, 570)**，用投递点击即可（/click）
- 点中后：僵尸数 0 → N、wave +1、challenge_state 变化

接口：

`json
POST /next_wave
→ {ok:true, zombies_before:0, zombies_after:5, wave_after:1, clicked:[400,570]}
`

## 三·补二十四 破罐者（Vasebreaker, game_mode 51）

- /state.vases 能读到**每个罐子的内容**（植物/普通僵尸/铁桶/小丑），可据此决定破罐顺序
- 破罐：POST /break_vase {row:R,col:C} → 用 Board::MouseDown 点格子中心
  （内部会校验罐子是否真的碎了）
- 罐子里的植物：打破后地上生成卡片（	ype=16 硬币，usable_seed_type = 植物类型）
- 种下植物卡：**点卡片 + 点目标格都必须用 Board::MouseDown**
  （投递窗口点击只能收卡、种不下去）

`json
POST /vase_plant {row:4, col:0}
→ {ok:true, type:5, name:寒冰射手, card_click:[380,180], cell_click:[80,490]}
`

实测：寒冰射手卡片 → 选中 (4,0) → 成功种下。

## 三、经济系统：桥自己记账（重要）

`Board::AddPlant`（远程调用）本身**不扣阳光、不进冷却**，所以桥替它记账，并且**写回游戏内存**让画面一致：

| 机制 | 做法 |
| --- | --- |
| 扣阳光 | 放置成功后 `g.sun = sun_before - 成本`（写内存） |
| 冷却（桥） | 桥内维护 `slot -> ready_at`，时长取 `PLANT_CD_MS` 表 |
| 冷却（游戏 UI） | 直接写种子槽：`cd_elapsed=0, cd_total=cd_cs, usable=0, refreshing=1` → 卡片变灰、走倒计时、到点自动恢复 |
| 门槛 | `usable = 游戏卡可用 && 桥冷却已过 && 阳光够成本` |

**种子槽地址**（1.0.0.1051）：

```text
app      = *(0x6A9EC0)
board    = *(app + 0x768)
seedBank = *(board + 0x144)
packet_i = seedBank + 0x28 + i*0x50
   +0x24 cd_elapsed(cs)   +0x28 cd_total(cs)
   +0x48 usable(byte)     +0x49 refreshing(byte)
```

阳光成本 `PLANT_COST`、冷却 `PLANT_CD_MS`：多数 7.5s，坚果/土豆雷/窝瓜/南瓜等 30s，
樱桃/寒冰菇/毁灭菇/辣椒/加农炮等 50s。

实测（2026-11-07）：

```text
种坚果 PLANT 200 {"ok":true,"charged":50,"sun":75,"cooldown_left_ms":28562}
  游戏种子槽  cd=78/3000   usable=0
  t=1s        cd=281/3000
  t=2s        cd=483/3000   桥 cd_left=22906ms
```

注意：**游戏暂停（窗口失焦）时种子槽不会推进**，画面也不会刷新；恢复前台后继续。
桥重启会清空本地冷却表，但游戏侧的冷却字段仍然有效（以游戏为准更准）。

| 能力 | 方式 |
| --- | --- |
| 读状态 | `ReadProcessMemory`（只读） |
| 种 / 铲 | **远程调用**游戏自己的函数（`pvztools` remote call） |
| 阳光 / 冷却 | 桥自己记账（见上一节） |
| 收阳光 | **不需要桥**：exe 已打字节补丁，游戏自己收 |

**没有用鼠标、没有用截图、没有 OCR。**

## 四、踩过的坑（写下来省时间）

1. **投递窗口消息不生效**：`PostMessage(WM_LBUTTONDOWN)` 在这版游戏里完全被忽略，
   实测点了没反应；**真实鼠标（`SetCursorPos`+`mouse_event`）有效**——
   选卡界面就是这么做的（见上面「选卡界面」一节）。
   注意：普通种植仍走远程调用，比鼠标准且不抢光标。
2. **DPI 虚拟化**：如果桥进程不 `SetProcessDpiAwareness`，`GetClientRect` 会返回 533×400，
   坐标校准得出假的 1.5 倍，点击全偏。
3. **`collect_all()` 不可用**：retail 家族 `coin_collect` 调用约定未验证，pvztools 直接拒绝。
   收阳光靠 exe 补丁解决（见 `客厅/待审/2026-11-07-PvZ1-自动收集mod/`）。
4. **pvztools 有进程锁**：同一个游戏进程只能有一个 pvztools 实例附着；跑测试前先停桥。
5. **游戏失焦会暂停**：已打 `background_running` 补丁，不支持时读到的 `paused` 会是 true。

## 五、已验证 / 未验证

已验证（2026-11-07 实机）：

- `/state` 全字段
- `/plant`（向日葵、大嘴花实测种下，类型核对一致）
- `/shovel`（实测铲掉，格子清空）
- 远程调用不影响游戏稳定性（连续操作数十次无崩溃）

未验证：

- 选卡界面（seed chooser）的自动化
- 关卡片 / 开始关卡
- 玉米炮、铲子外的其它道具
- 长时间（小时级）稳定性

## 六、最小用法

```python
import json, urllib.request

B = 'http://127.0.0.1:15580'

def state():
    with urllib.request.urlopen(B + '/state', timeout=10) as r:
        return json.loads(r.read().decode('utf-8'))

def post(path, body):
    req = urllib.request.Request(B + path, data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))

s = state()
if s['sun'] >= 50 and any(x['name'] == '向日葵' and x['usable'] for x in s['seeds']):
    post('/plant', {'row': 0, 'col': 0, 'plant': '向日葵'})
```

——续灯（AI 助手）
