# 变更记录

## v2026-11-12

### 新增：小游戏支持

| 关卡 | 新接口 |
| --- | --- |
| 老虎机（mode 18） | `/spin`、`/plant_prize` |
| 雨关（mode 19） | `/plant_prize` |
| 宝石迷阵（mode 20） | `/begh_swap` |
| 宝石迷阵 Twist（mode 24） | `/twist_rotate`（**新**） |
| 谁笑到最后（mode 31） | `/next_wave`（**新**） |
| 破罐者（mode 51） | `/break_vase`、`/vase_plant`（**新**） |
| 保护传送门（mode 26） | `/state.grid_items` 可读传送门（含第 9 列） |

### 新增：通用接口

- `/debug_click`：远程 `Board::MouseDown`
- `/click`：通用点击（默认走棋盘点击，可 `method:"post"` 回退）
- `/force_plant`：强制放置（跳过卡槽/阳光校验，调试用）
- `/belt_compact`：传送带手动补位
- `/recalibrate`：窗口/全屏切换后校准坐标

### 修复

1. **传送带不补位**（重要）
   - 现象：种掉一张卡后，后面的卡不往前补，偶尔新卡"穿过"前卡填空位
   - 原因：桥绕过游戏 UI 直接 `AddPlant`，游戏不知道卡被用掉
   - 修复：传送带关改走"点卡 → 点格子"UI 路径 + 种下瞬间 `compact_belt()`（`offset += 50*N`）
2. **全屏模式下点击失效**
   - 原因：投递窗口消息的坐标不被采用（游戏读真实光标）
   - 修复：主要交互改为直接调用 `Board::MouseDown` / `WidgetManager::MouseDown`
3. **传送门读不到（第 9 列被过滤）**
   - `read_grid_items` 原来限定 `col <= 8`，放宽到 `col <= 12`
4. **`/plant` 传送带分支未定义变量 `bd`**，导致 UI 点击抛异常后静默走兜底路径

### 文档

- `README.md`：新增"三·补十七 ~ 三·补二十四"共 8 节，记录老虎机、雨关、宝石迷阵、Twist、传送带补位、Last Stand、破罐者等实现与踩坑
- `API.md`：新增 v2026-11-12 接口章节
- `AGENTS.md`：新增第 10 节"小游戏模式"
- `DESIGN-NOTES.md`：新增架构分层、结构偏移、三种点击实现、各模式入口

## v2026-11-08

首个开源版本：状态读取 + 种植/铲除 + 选卡 + 特殊场景校验（池塘/屋顶/冰面/墓碑）。
