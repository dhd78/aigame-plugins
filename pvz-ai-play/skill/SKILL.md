---
name: pvz-play
description: Play and inspect Plants vs. Zombies 1.0.0.1051 through a local HTTP bridge that exposes the board as JSON and accepts plant, shovel, pick, start and minigame actions. Use when the user asks to automate PvZ, read the PvZ board, plant or shovel in Plants vs. Zombies, play PvZ minigames (slot machine, Vasebreaker, Beghouled/Twist), or build an agent that plays PvZ.
license: MIT
---

# pvz-play

## 这个技能做什么

把 Windows 上的《植物大战僵尸》1.0.0.1051（英文零售版）包装成一个本机 HTTP 服务：agent 用 `GET /state` 读棋盘（阳光、卡片、植物、僵尸、障碍、传送带、小游戏状态等），用 `POST /plant`、`/shovel`、`/pick`、`/start` 以及小游戏端点操作。不需要截图、OCR 或鼠标控制。

桥是单文件 Python（`src/pvz_server.py`），只监听 `127.0.0.1:15580`；游戏由用户自备，本包不含游戏本体、素材或存档。

> **版本**：技能 `0.1.2` ↔ 桥 `0.2.0`。
> 已支持除僵尸水族馆和锤僵尸之外的所有游戏模式。目前没有让 AI 自己选关卡的接口：需要人类先在游戏里选好关卡，再由 AI 接管。

> ⚠ **这个技能会改游戏状态，也会写游戏内存**：`/plant` 会扣阳光、把卡片冷却写回游戏内存（让卡片 UI 正常变灰），并写入少量种植初始化字段；`/shovel`、`/pick`、`/start` 及小游戏端点会改变游戏状态。只用于**单机离线**、用户自己的正版游戏；不要用于联机 / 竞技 / 修改存档。

## 环境

| 项 | 要求 |
| --- | --- |
| 系统 | Windows（ctypes + Win32 API；macOS / Linux 不支持） |
| Python | 3.9+（3.10 / 3.11 实测；本包未在 3.12 实测） |
| 依赖 | `pvztools >= 0.2.0`（MIT），`pip install pvztools` 或 `PVZTOOLS_VENDOR` |
| 游戏 | **PvZ 1.0.0.1051 英文零售版**，`PlantsVsZombies.exe` 3,007,800 字节，用户自备正版 |
| 端口 | `127.0.0.1:15580` |

## 坐标

**行 0..4（池塘/浓雾为 0..5），列 0..8，全部 0 基；行 0 最上，列 0 最左。**

- 屋顶：**5 行**（0..4），只有有花盆（type 33）的格子能种；
- 池塘/浓雾：**6 行**（0..5），第 2、3 行是水面。

像素换算（`/click`、`/debug_click` 用，格子左上角）：

```text
白天/夜晚：x = 40 + col*80    y = 80 + row*100
池塘/浓雾：x = 40 + col*80    y = 80 + row*85
屋顶：     x = 40 + col*80    y = 70 + row*85 + (col<5 ? (5-col)*20 : 0)
```

点中心再加 `x+40`、`y+半格`。

## 安装

```powershell
# 1. 安装依赖（或设置 PVZTOOLS_VENDOR 指向离线目录）
pip install "pvztools>=0.2.0"

# 2. 启动桥
python src\pvz_server.py 15580

# 3. 健康检查与读状态
Invoke-RestMethod http://127.0.0.1:15580/health
Invoke-RestMethod http://127.0.0.1:15580/state
```

游戏需先启动并进入关卡；桥按进程查找 `PlantsVsZombies.exe`。完整字段、409 reason 与主循环见 `references/AGENTS.md` 和 `references/API.md`。

## 端点

### 基础

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/health` | 服务信息 |
| GET | `/state` | 完整棋盘 JSON |
| POST | `/plant` | `{"row":1,"col":8,"plant":"向日葵"}`；扣阳光、进冷却 |
| POST | `/shovel` | `{"row":1,"col":8}` |
| POST | `/pick` | 选卡界面选卡 `{"seeds":[...]}` |
| POST | `/start` | 开始关卡 |
| POST | `/continue` | 结算/主菜单推进（实验性，坐标未校准） |

### 点击 / 调试

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/click` | 通用点击，默认 `Board::MouseDown`；可传 `"method":"post"` 回退 |
| POST | `/debug_click` | **调试接口**，不写进主流程 |
| POST | `/force_plant` | **调试接口**，跳过卡槽/阳光/冷却，不写进主流程 |
| POST | `/recalibrate` | 窗口/全屏切换后重校准回退点击 |

### 小游戏

| 模式 | 端点 |
| --- | --- |
| 老虎机 | `POST /spin` |
| 宝石迷阵 | `POST /begh_swap {"row1","col1","row2","col2"}`；**全屏可能失效**（仍依赖投递消息） |
| 宝石迷阵 Twist | `POST /twist_rotate {"row","col"}`（2×2 左上角） |
| 破罐者 | `POST /break_vase {"row","col"}`；`POST /vase_plant {"row","col","type"?}` |
| 谁笑到最后 | `POST /next_wave` |
| 雨关 / 老虎机奖品 | `POST /plant_prize {"row","col","type"?}` |
| 传送带 | `POST /belt_compact {"slots"?}`（`/plant` 通常自动补位，一般不用） |

## 主循环

```text
while True:
  s = GET /state
  if s.ui == "选卡界面": POST /pick; POST /start; continue
  if not s.in_level: break

  if s.vases:                 # 破罐者
      POST /break_vase; POST /vase_plant; continue
  if s.challenge 有分数变化:   # 宝石迷阵 / Twist
      POST /begh_swap 或 /twist_rotate; continue
  if s.coins 有可种卡片:       # 老虎机 / 雨关
      POST /plant_prize; continue
  if s.conveyor:              # 传送带
      POST /plant（用 s.belt 里的卡）
  else:
      POST /plant 可种格子里成本最低的卡
  sleep 1.5
```

小游戏不要求写完整策略，给端点即可；每一轮都重读 `/state`，不要缓存棋盘。完整分支见 `references/AGENTS.md` 第 10 节。

**收到 409 不要原样重试**：按 `reason` 换卡 / 换格 / 等待，完整映射见 `references/AGENTS.md`。

## 失败怎么办

| 现象 | 处理 |
| --- | --- |
| `ModuleNotFoundError: pvztools` | `pip install "pvztools>=0.2.0"`，或设 `PVZTOOLS_VENDOR` 指向离线目录 |
| `/state` 500 | 游戏没开 / 不是 1.0.0.1051 / 游戏进程名不对；先手动进关卡 |
| `/plant` 一直 `cooldown` | 桥重启会清空本地冷却表；以 `/state.seeds[].cooldown_left_ms` 为准 |
| 端口占用 | 换端口 `python src\pvz_server.py 15581`，但技能默认 15580 |
| 游戏崩溃后状态丢 | 重启游戏，桥按 pid 自动重挂；当前关卡进度会丢 |
| 中文卡名不匹配 | 英文版游戏也可用中文卡名（桥内映射表），但其他语言构建未测 |
| `/begh_swap` 全屏无效 | 切窗口模式，或改用 `/click` 手动点（`/begh_swap` 仍是投递实现） |
| 小游戏模式判断不了 | `/state` 没有 `game_mode`；看 `vases` / `belt` / `challenge.score` 特征 |

## 边界

- **单机离线**：只操作本机游戏进程；不联网、不联机、不碰存档文件。
- **不改 exe**：`references/AUTO-COLLECT-SUN.md` 里的两个补丁是**可选**的，且只写说明与数值；本包不包含 exe、不自动打补丁。打补丁前必须备份，风险自负。
- **写回是设计的一部分**：`/plant` 的阳光扣费 / 冷却写回属本技能的已知行为；介意写内存就不要用这个技能。
- **本地 HTTP 无鉴权**：任何本机进程都能读当前棋盘、发操作；不要转发端口、不要暴露到局域网。
- 只支持 1.0.0.1051；GOTY 1.2.0.1096 不支持。
- `/debug_click`、`/force_plant` 是调试接口，不写进主流程；`/begh_swap` 全屏可能失效。
- 不打包游戏本体、素材、存档、exe 补丁。

## 许可 / 声明

- 代码：MIT，见 `LICENSE`（版权：dhd；实现参与见 `AI-DISCLOSURE.md`）；
- 第三方：`pvztools` MIT，见 `THIRD_PARTY_NOTICES.md`；
- 游戏与补丁：不在包内，用户自备并遵守游戏 EULA；
- AI 参与：见 `AI-DISCLOSURE.md`；来源与重建：见 `SOURCE.md`。

## English

`pvz-play` exposes *Plants vs. Zombies* 1.0.0.1051 (English retail, user-supplied) as a local JSON HTTP service on `127.0.0.1:15580`. An agent can read the board (`GET /state`) and act (`POST /plant`, `/shovel`, `/pick`, `/start`) plus minigame endpoints without screenshots or OCR.

**Version**: skill `0.1.2` ↔ bridge `0.2.0`. All game modes except Zombiquarium and Zombie Nimble Zombie Quick are supported; there is no API to choose a level — a human must select the level, then the agent takes over.

**This skill changes game state and writes game memory**: planting deducts sun and writes seed cooldowns / plant-init fields back into the game process. Use only on a single-player, offline, legitimately owned copy. The game is not bundled. Requires Windows, Python 3.9+, and `pvztools>=0.2.0`. Coordinates are 0-based: rows 0..4 (pool/fog 0..5), columns 0..8. `/debug_click` and `/force_plant` are debug-only and not part of the main loop; `/begh_swap` may fail in fullscreen. Optional exe patch notes are in `references/AUTO-COLLECT-SUN.md`; the package contains no executable patch.
