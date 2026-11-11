---
name: farmer-bridge
description: Read farm state and run code in The Farmer Was Replaced through a local BepInEx bridge on 127.0.0.1:15800. Use when the user asks to read farm state, automate The Farmer Was Replaced, run game code, send a drone, or inspect the tech tree. 当用户要求读取农场状态、自动化《编程农场》、运行游戏代码、派出无人机或查看科技树时使用。
license: MIT
---

# FarmerBridge

《编程农场》（*The Farmer Was Replaced*）的本地桥技能：游戏侧是 BepInEx 插件 `FarmerBridge.dll`，把模拟状态暴露成 `127.0.0.1:15800` 的 JSON；本技能只负责让 agent 知道**怎么装、怎么读、怎么写代码并运行**。

- 不截图、不做 OCR、不模拟鼠标键盘；
- 不携带 DLL / BepInEx / 游戏文件；这些由用户自己安装；
- 不启动游戏；游戏必须由用户手动打开。

## 前置检查

先请求：

```text
GET http://127.0.0.1:15800/health
```

期望：

```json
{"ok": true, "bridge": "farmer-bridge", "version": "0.1.3", "port": 15800}
```

**不通时，按两条路径判断：**

| 现象 | 判断 | 处理 |
| --- | --- | --- |
| 连接被拒绝 / 超时，游戏进程不存在 | 游戏没开 | 先手动启动游戏；游戏进存档后桥才会监听 |
| 游戏已开、`/health` 仍不通 | DLL 没装 / BepInEx 没装 / 放错目录 | 按 `references/INSTALL.md` 重装；看 `<游戏目录>\BepInEx\LogOutput.log` 是否有 `FarmerBridge listening on 127.0.0.1:15800` |
| `/health` 通、`/state` 500 | 还在主菜单 / 没进存档 | 进存档后再试；必要时 `POST /start` 加载存档 |

## 环境

| 项 | 要求 |
| --- | --- |
| 系统 | **Windows only**（BepInEx + Unity x64） |
| 游戏 | *The Farmer Was Replaced*，用户自备 |
| 桥 | BepInEx **5.4.23.6 x64** + `FarmerBridge.dll`（用户安装，本包不带） |
| 桥版本 | FarmerBridge 0.1.3 或更新（含 `/start`） |
| Python | 3.9+（客户端只用标准库） |
| 端口 | `127.0.0.1:15800`（仅回环，无鉴权） |

## 安装（用户侧）

1. 把 **BepInEx 5.4.23.6 x64** 解压到游戏根目录（与 `TheFarmerWasReplaced.exe` 同级）；
2. 把 `FarmerBridge.dll` 放到 `<游戏目录>\BepInEx\plugins\`；
3. 启动游戏，日志出现 `FarmerBridge listening on 127.0.0.1:15800`；
4. 运行 `python scripts/farmer.py state` 验证。

完整步骤、卸载与排错见 `references/INSTALL.md`。

## 端点

所有请求只发往 `http://127.0.0.1:15800`，JSON。

### 读

| 端点 | 作用 |
| --- | --- |
| `GET /health` | 桥版本与状态 |
| `GET /state` | 农场 / 无人机 / 时间 / 执行状态总览 |
| `GET /grid?x=0&y=0&w=8&h=8` | 地表矩形；加 `&depth=N` 读地下层 |
| `GET /drones` | 无人机位置与深度 |
| `GET /items` | 物品数量 |
| `GET /unlocks` | 已解锁项 |
| `GET /tech` | 科技树、等级、价格、DLC 标记 |
| `GET /doc?page=docs/...` | 游戏内文档 |
| `GET /files` | 代码文件列表 |
| `GET /execution` | 当前执行状态 |
| `GET /output` | 游戏输出（`print` 等） |

### 写 / 执行

| 端点 | 作用 | 注意 |
| --- | --- | --- |
| `POST /file {"name":"maze"}` | 创建/选择代码页 | 文件名限字母数字 `_` `-`，≤32 字符 |
| `POST /code {"file":"main","source":"..."}` | 写入代码 | 默认页 `main` |
| `POST /run {"file":"main"}` | 运行代码 | 会改游戏状态 |
| `POST /stop` | 停止 | — |
| `POST /step` | 单步 | — |
| `POST /buy {"name":"loops"}` | 按游戏规则买科技 | **扣材料**，先确认 |
| `POST /save` | 存档 | 异步，不等待磁盘完成 |
| `POST /load` | 读当前存档 | 重建 sim / 代码窗口 |
| `POST /start {"save":"名字"}` | 加载存档并进入游戏 | 存档名可含中文 |

> **调试写接口默认关闭**：只有设置 `FARMERBRIDGE_DEBUG=1` 才会启用开发者用的写接口。本技能**不使用、也不在文档里介绍**这些接口；普通使用不需要设置该变量。

## 主循环

```text
GET /health
  → GET /state          看时间、无人机、是否在执行
  → GET /grid           看地块（需要地下时加 depth）
  → POST /code          把代码写入 main / maze
  → POST /run           运行
  → GET /output         读 print 输出
  → GET /execution      看是否还在跑
```

## 客户端

```powershell
python scripts\farmer.py state
python scripts\farmer.py grid --x 0 --y 0 --w 8 --h 8
python scripts\farmer.py grid --x 0 --y 0 --w 8 --h 8 --depth 16
python scripts\farmer.py code --file my_code.py --name main
python scripts\farmer.py run --name main
python scripts\farmer.py output
python scripts\farmer.py tech
python scripts\farmer.py doc docs/scripting/while.md
```

`--help` 查看全部命令。客户端只用 Python 标准库，无第三方依赖。

## 最小示例

```python
# examples/inspect_state.py
from farmer import api
print(api("/state"))
print(api("/grid?x=0&y=0&w=8&h=8"))
```

```python
# examples/run_code.py
from farmer import api
api("/code", "POST", {"file": "main", "source": "do_a_flip()"})
api("/run", "POST", {"file": "main"})
print(api("/output"))
```

## 安全 / 边界

- 桥只绑定 `127.0.0.1`、无鉴权，**不要端口转发到局域网/公网**；
- `/code` / `/run` / `/buy` / `/save` 会改游戏状态或存档，执行前让用户确认；
- 本包不含 `FarmerBridge.dll`、BepInEx、游戏本体、存档、素材；
- 只支持 Windows；游戏更新后类型/字段可能变化，桥可能失效，需等插件更新；
- 不要在公开文档里写调试写接口的用法。

## 失败怎么办

| 现象 | 处理 |
| --- | --- |
| `连不上 FarmerBridge` | 按“前置检查”两条路径：游戏没开 / DLL 没装；看 `LogOutput.log` |
| `/state` 500 | 游戏还在主菜单；进存档或 `POST /start` |
| `/run` 返回 404 | 先 `POST /file` 建代码页，或检查 `file` 名 |
| `/output` 空 | 代码还没 `print`，或执行未结束；看 `/execution` |
| 端口冲突 | 确认没有第二个桥/进程占用 15800；桥只支持单实例 |

## English

`farmer-bridge` is a Windows-only skill for *The Farmer Was Replaced*. A BepInEx 5.4.23.6 plugin (`FarmerBridge.dll`, installed by the user) exposes the game's farm state over a loopback JSON API at `127.0.0.1:15800`; this skill teaches an agent how to verify the bridge, read state/grid/tech, write code to a file page, run it, and read output. It does not bundle the DLL, BepInEx, game files or saves, and does not start the game.

Triggers: read farm state, automate The Farmer Was Replaced, run game code, send a drone, inspect tech tree.

**Loopback only, no authentication.** Do not expose the port. `/code`, `/run`, `/buy` and `/save` change game state or the save; confirm with the user first. Debug write endpoints are off unless `FARMERBRIDGE_DEBUG=1`; this skill does not use or document them.

See `references/INSTALL.md` and `references/API.md`.
