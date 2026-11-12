# PvZ1 桥（状态 + 动作）

把 Windows 上的《植物大战僵尸》1.0.0.1051（英文零售版）包装成本机 HTTP 服务：agent 通过 JSON 读棋盘、种植物、铲植物、选卡、开局，并驱动大部分小游戏。不需要截图、OCR 或鼠标控制。

| 项 | 值 |
| --- | --- |
| 版本 | `0.2.0`（2026-11-12） |
| 端口 | `http://127.0.0.1:15580` |
| 游戏 | Plants vs. Zombies 1.0.0.1051（英文零售版，用户自备） |
| 系统 | Windows |
| Python | 3.9+ |
| 依赖 | `pvztools >= 0.2.0` |
| 作者 | 续灯（AI 助手）；发布：dhd |

## 一、能做什么

- 读棋盘：阳光、波次、卡片、冷却、植物、僵尸、硬币、场地物品、冰面、水面、花盆、罐子、传送门、小游戏状态；
- 操作：选卡、开局、种植、铲除、结算推进；
- 小游戏：老虎机、雨关、宝石迷阵、宝石迷阵 Twist、谁笑到最后、破罐者、保护传送门、传送带类关卡；
- 窗口模式和全屏模式都能用（点击走游戏自身的处理函数，不依赖投递消息）。

**版本覆盖说明**：本版本已支持除**僵尸水族馆（Zombiquarium）**和**锤僵尸（Whack a Zombie）**之外的所有游戏模式。

**关卡选择**：目前**没有让 AI 自己选关卡的接口**。需要人类先在游戏里选好关卡、进入关卡，再由 AI 接管操作。选卡界面可以用 `/pick` + `/start`，但“从主菜单挑哪个模式”仍需人工。

## 二、安装与启动

```powershell
# 1. 安装依赖（或用 PVZTOOLS_VENDOR 指向离线目录）
pip install "pvztools>=0.2.0"

# 2. 启动游戏，进入一个关卡

# 3. 启动桥
python pvz_server.py 15580
```

启动后先确认：

```powershell
Invoke-RestMethod http://127.0.0.1:15580/health
# {"ok": true, "service": "pvz-bridge", "port": 15580}
```

如果 `/state` 一直 500：检查游戏是否在运行、版本是否为 1.0.0.1051。

## 三、接口总览

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/health` | 健康检查 |
| GET | `/state` | 完整棋盘状态 |
| POST | `/pick` | 选卡界面选卡 |
| POST | `/start` | 选卡界面开始关卡 |
| POST | `/plant` | 种一棵植物 |
| POST | `/shovel` | 铲掉一格植物 |
| POST | `/continue` | 结算/主菜单推进（实验性，坐标未校准） |
| POST | `/spin` | 老虎机拉杆（mode 18） |
| POST | `/plant_prize` | 种奖品/雨关卡片（mode 18、19） |
| POST | `/begh_swap` | 宝石迷阵交换（mode 20） |
| POST | `/twist_rotate` | 宝石迷阵 Twist 旋转 2×2（mode 24） |
| POST | `/next_wave` | 谁笑到最后：继续猛攻（mode 31） |
| POST | `/break_vase` | 破罐者：敲罐（mode 51） |
| POST | `/vase_plant` | 破罐者：种罐子里的植物（mode 51） |
| POST | `/debug_click` | 直接调用棋盘点击处理（逻辑坐标） |
| POST | `/click` | 通用点击（默认棋盘点击，可回退投递） |
| POST | `/force_plant` | 跳过校验强制放置（调试用） |
| POST | `/belt_compact` | 传送带手动补位 |
| POST | `/recalibrate` | 窗口/全屏切换后重新校准 |

坐标：**行 0..4（池塘/浓雾为 0..5），列 0..8，全部 0 基；行 0 是最上面一行，列 0 是最左边一列。**

自己算像素坐标（`/click`、`/debug_click` 用，格子左上角）：

```text
白天/夜晚：x = 40 + col*80    y = 80 + row*100
池塘/浓雾：x = 40 + col*80    y = 80 + row*85
屋顶：     x = 40 + col*80    y = 70 + row*85 + (col<5 ? (5-col)*20 : 0)
```

点格子中心再加：`x + 40`、`y + 格高/2`。

## 四、读状态：`GET /state`

主要字段：

| 字段 | 说明 |
| --- | --- |
| `ok` | 是否成功 |
| `pid` | 游戏进程 id（桥重挂后会变） |
| `version` | pvztools 的 profile id（如 `1_0_0_1051_en`），不是游戏字段 |
| `ui` | `主菜单` / `选卡界面` / `关卡中` / `通关结算` / `未知(...)` |
| `in_level` | 是否在关卡内（选卡界面也算 true） |
| `paused` | 游戏是否暂停（失焦会暂停） |
| `sun` | 阳光 |
| `wave` | 当前波次 |
| `scene` | `0` 白天 / `1` 夜晚 / `2` 池塘 / `3` 浓雾 / `4` 屋顶 |
| `is_pool` | 池塘/浓雾（有水面） |
| `conveyor` | 传送带关 |
| `chooser_picked` | 选卡界面已选数量 |

卡片 `seeds[]`：`slot`、`type`、`name`、`cost`、`game_usable`、`cooldown_left_ms`、`affordable`、`usable`、`on_belt`。普通关看 `usable`；传送带关看 `belt`。

植物 `plants[]`：`row`、`col`、`type`、`name`、`hp`、`index`。花盆（33）和荷叶（16）与植物同格共存。

僵尸 `zombies[]`：`row`、`x`（像素）、`type`、`name`、`hp`、`max_hp`、`helmet_hp`、`shield_hp`、`status`、`altitude`、`flying`、`has_object`、`in_pool`、`mind_controlled`、`target_row/col`。`flying == true` 是气球僵尸，普通豌豆打不到。

场地：`grid_items[]`（墓碑 1、弹坑 2、梯子 3、传送门 4/5、罐子 7、蜗牛 10、钉耙 11、脑子 12）、`blocked`（不能种的格子）、`ice`/`ice_rows`（雪橇车冰面）、`water`/`lily`/`pots`（水面、荷叶、花盆）、`belt`/`belt_ready`（传送带）、`vases`（罐子内容）、`coins[]`（可拾取物，`type==16 && seed_type>=0` 是植物卡片）、`challenge{state,counter,score,sel_flag,sel_x,sel_y}`（小游戏状态机）。

## 五、基础操作

### 选卡 `POST /pick`

```json
{"seeds": ["小喷菇","向日葵","豌豆射手","坚果","寒冰射手","樱桃炸弹"]}
→ {"ok": true, "picked": [...], "picked_count": 6, "bank_size": 6, "cleared_ok": true, "failed": []}
```

卡槽比传入多时会自动补满；不在选卡界面返回 409。

### 开局 `POST /start`

```json
{"wait": 20}
→ {"ok": true, "ui": 3}
```

点「Let's Rock!」并等待界面切换。

### 种植 `POST /plant`

```json
{"row": 1, "col": 8, "plant": "向日葵", "wait": 10}
→ {"ok": true, "placed": "向日葵", "charged": 50, "sun_before": 200, "sun": 150,
   "cooldown_left_ms": 7436, "index": 12}
```

`wait` 可选：卡不可用时最多等多少秒。

失败返回 409，`reason` 与处理建议：

| reason | 含义 | 建议 |
| --- | --- | --- |
| `cooldown` | 冷却中 | 换卡或等待 |
| `no_sun` | 阳光不够 | 等阳光或先种产阳光植物 |
| `card_not_usable` | 游戏层面不可用 | 换卡 |
| `occupied` | 格子已有植物 | 换格子 |
| `blocked` | 墓碑/弹坑/梯子/罐子 | 换格子 |
| `ice` | 雪橇车冰面 | 换格子（约 30 秒化） |
| `needs_lilypad` | 水面缺荷叶 | 先种荷叶 |
| `needs_flowerpot` | 屋顶缺花盆 | 先种花盆 |
| `water_only` | 水生植物种到陆地 | 换水面格 |
| `buster_needs_grave` | 墓碑吞噬者不在墓碑上 | 找 `grid_items type==1` |
| `not_on_belt` | 传送带没有这张卡 | 从 `belt` 里挑 |

植物不在卡槽 → 404。

### 铲除 `POST /shovel`

```json
{"row": 1, "col": 8} → {"ok": true, "removed": "向日葵"}
```

### 结算推进 `POST /continue`

实验性：坐标未校准，结算界面目前建议人工点击。

## 六、小游戏接口

### 老虎机（mode 18）

```json
POST /spin {"wait": 1.0}
POST /plant_prize {"row": 1, "col": 3, "type": 5}
```

奖品是弹出的植物卡片（`coins` 里 `type==16 && seed_type>=0`），三张卷轴图案只是动画。

### 雨关（mode 19）

```json
POST /plant_prize {"row": 1, "col": 3}
```

卡片从天上掉，读 `coins` 后种下；水生植物只能种水里。

### 宝石迷阵（mode 20）

```json
POST /begh_swap {"row1": 2, "col1": 3, "row2": 2, "col2": 4}
```

交换相邻两格凑三连。**该接口仍用投递消息，全屏模式下可能失效。**

### 宝石迷阵 Twist（mode 24）

```json
POST /twist_rotate {"row": 2, "col": 3, "wait": 0.7}
→ {"ok": true, "game_mode": 24, "click": [311, 320], "sun_gain": 25}
```

顺时针旋转以 `(row,col)` 为左上角的 2×2。无效旋转游戏会自己转回去，调用后读 `/state` 确认。

### 谁笑到最后（mode 31）

```json
POST /next_wave
→ {"ok": true, "zombies_before": 0, "zombies_after": 5, "wave_after": 1}
```

点「继续猛攻」提前拉下一波。

### 破罐者（mode 51）

```json
POST /break_vase {"row": 3, "col": 6}
→ {"ok": true, "content": "plant", "detail": "豌豆射手"}

POST /vase_plant {"row": 4, "col": 0, "type": 5}
→ {"ok": true, "name": "寒冰射手", "planted": {"row": 4, "col": 0, "type": 5, "hp": 300}}
```

罐子内容可提前从 `/state.vases` 读取，用于决定先敲哪个。

### 保护传送门（mode 26）

`/state.grid_items` 可直接读到 4 个传送门（含第 9 列）。

## 七、通用与调试接口

| 接口 | 用法 |
| --- | --- |
| `POST /debug_click` | `{"x":480,"y":290}`，调用 `Board::MouseDown`，棋盘逻辑坐标 |
| `POST /click` | 同上；`{"method":"post"}` 回退到投递消息 |
| `POST /force_plant` | `{"row":0,"col":6,"type":33}`，跳过卡槽/阳光/冷却校验 |
| `POST /belt_compact` | 传送带手动补位；正常 `/plant` 会自动补，一般不用 |
| `POST /recalibrate` | 窗口/全屏切换后校准回退点击的坐标映射 |

## 八、场景与规则

- **传送带关**：`conveyor: true`，`seeds[].cost` 全为 0；从 `belt` 挑卡，用掉后约 10 秒补新卡，每次循环重读 `/state`；
- **池塘/浓雾**：`is_pool: true`，水面是第 2、3 行；陆生植物需先有荷叶（`lily`）；荷叶/缠绕水草/海蘑菇/香蒲只能种水里；
- **屋顶**：`scene: 4`，只有 `pots` 里的格子能种普通植物；花盆会被砸掉，逐格重读；
- **打罐子**：罐子算 `blocked`，内容可读，先敲再种；
- **空中僵尸**：`flying == true`，需要仙人掌/三叶草/香蒲等对空植物；
- **经济**：普通关 `/plant` 真扣阳光并把冷却写回游戏；传送带关不扣阳光、不进冷却。

## 九、已知限制

- 依赖 `pvztools >= 0.2.0`（计划后续去掉，改为自研内存层）；
- `/begh_swap` 仍用投递消息，全屏模式可能失效；
- 只支持 PvZ 1.0.0.1051（英文零售版），Windows + Python 3.9+；
- 僵尸水族馆、锤僵尸两个模式未适配；
- **没有 AI 选关接口**：关卡由人类选好，AI 接管；
- 结算界面坐标未校准，建议人工点击；
- 写操作会改变游戏状态（阳光、冷却、种植、小游戏分数），只用于单机本地。

## 十、许可与第三方

MIT，见 `LICENSE`。`pvztools`、BepInEx 等第三方组件保留各自许可；本仓库不包含游戏本体、素材、存档或可执行文件。见 `THIRD_PARTY_NOTICES.md`。
