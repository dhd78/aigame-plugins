# pvz-play

把《植物大战僵尸》1.0.0.1051（Windows 英文零售版）包装成本机 HTTP 服务，让 agent 读棋盘并操作，含小游戏端点。

**English:** `pvz-play` turns *Plants vs. Zombies* 1.0.0.1051 into a local JSON HTTP service on `127.0.0.1:15580`: `GET /state` returns the board, and `POST /plant`, `/shovel`, `/pick`, `/start` plus minigame endpoints act without screenshots or OCR. **It changes game state and writes game memory** (sun deduction, seed cooldowns, plant-init fields). Single-player, offline, user-supplied game only.

- 版本：技能 `0.1.2` ↔ 桥 `0.2.0`
- 入口：`python src\pvz_server.py 15580`
- 依赖：Python 3.9+；`pvztools>=0.2.0`（MIT）
- 游戏：用户自备 PvZ 1.0.0.1051；本包不含游戏本体 / 素材 / 存档 / exe 补丁
- 平台：Windows（ctypes + Win32 API）

## 0.2.0 有什么

- 新增小游戏端点：`/spin`、`/begh_swap`、`/twist_rotate`、`/break_vase`、`/vase_plant`、`/next_wave`、`/plant_prize`、`/belt_compact`；
- 全屏兼容：点击改走 `Board::MouseDown` / `WidgetManager::MouseDown`，旧投递为回退；
- 新端点：`/click`、`/debug_click`、`/force_plant`、`/recalibrate`；
- `/state` 新增 `challenge`、`coins[]`、`vases[]`、`belt_ready[]` 等字段；
- 已支持除僵尸水族馆和锤僵尸之外的所有游戏模式；没有让 AI 自己选关卡的接口，需人类先选关，再由 AI 接管。

## 包内容

```text
pvz-play/
├─ SKILL.md                     # 技能说明（frontmatter: name / description / license）
├─ README.md                    # 本文件
├─ src/pvz_server.py            # 0.2.0 完整桥（原样，未裁剪）
├─ scripts/smoke_test.py        # /health、/state 冒烟
├─ requirements.txt             # pvztools>=0.2.0
├─ references/
│  ├─ AGENTS.md                 # agent 主循环、409、特殊关卡、小游戏（第 10 节）
│  ├─ API.md                    # 0.2.0 端点与字段
│  ├─ DESIGN-NOTES.md           # 实现原理与内存布局
│  └─ AUTO-COLLECT-SUN.md       # 可选 exe 补丁说明（只文本，不含 exe）
├─ examples/README.md           # 最小调用示例
├─ LICENSE                      # MIT（Copyright dhd；实现参与见 AI-DISCLOSURE）
├─ AI-DISCLOSURE.md
├─ THIRD_PARTY_NOTICES.md       # pvztools MIT
└─ SOURCE.md                    # 上游对应 / 版本 / 未验证项
```

## 坐标

行 0..4（池塘/浓雾 0..5），列 0..8，全部 0 基；行 0 最上，列 0 最左。

- 屋顶 5 行（0..4），只有有花盆（type 33）的格子能种；
- 池塘/浓雾 6 行（0..5），第 2、3 行是水面。

像素换算（`/click`、`/debug_click` 用，格子左上角）：

```text
白天/夜晚：x = 40 + col*80    y = 80 + row*100
池塘/浓雾：x = 40 + col*80    y = 80 + row*85
屋顶：     x = 40 + col*80    y = 70 + row*85 + (col<5 ? (5-col)*20 : 0)
```

## 快速开始

```powershell
pip install "pvztools>=0.2.0"
python src\pvz_server.py 15580
Invoke-RestMethod http://127.0.0.1:15580/health
Invoke-RestMethod http://127.0.0.1:15580/state
```

游戏需先启动并进入关卡。完整主循环、409 处理与小游戏分支见 `references/AGENTS.md`。

## 会改游戏状态（务必先读）

- `/plant`：扣阳光、写卡片冷却、写少量种植初始化字段（让卡片 UI 正常变灰）；
- `/shovel`、`/pick`、`/start`、小游戏端点：改变游戏状态；
- 只用于**单机离线**、自己的正版游戏；不要用于联机 / 竞技 / 改存档。

## 调试接口

`/debug_click`、`/force_plant` 是调试接口，**不写进主流程**；正常流程用 `/plant`、`/shovel`、`/pick`、`/start`、小游戏端点。`/begh_swap` 仍依赖投递消息，**全屏模式下可能失效**。

## 验证状态（候选包 v0.1.2）

- 桥 0.2.0 由 14 发布（Release `pvz-ai-play-v0.2.0`）；本包按上游 zip 原样收录 `src/pvz_server.py`（79,170 B）；
- 已做：`py_compile`、端点表对照（0.2.0 全部端点）、`--help` / 语法、无二进制、SHA256SUMS、确定性 zip、干净解压；
- **未做**：本机无 `pvztools`，未在真实游戏实跑 `/health` `/state` `/plant` / 小游戏；未在真实 Claude Code / Cursor 安装中验证。
- 发布前建议 03 / 00 在已装 `pvztools` 的真实游戏环境回归。

## 来源

上游：`aigame-plugins/pvz-ai-play`（14-软件开发师·续灯）。本包按 `pvz-ai-play-v0.2.0.zip`（SHA `0E885557…EDFF`）收录；技能层由 17 整理。版本对应、文件 SHA、未验证项见 `SOURCE.md`。

## 许可

MIT，见 `LICENSE`（`Copyright (c) 2026 dhd`；实现参与记录在 `AI-DISCLOSURE.md`，不进 LICENSE）。`pvztools` 为 MIT，见 `THIRD_PARTY_NOTICES.md`。游戏本体与补丁不随包分发。
