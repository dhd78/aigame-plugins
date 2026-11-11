# farmer-bridge

`The Farmer Was Replaced`（编程农场）的本地桥技能。

游戏侧是一个 BepInEx 插件 `FarmerBridge.dll`：它在游戏进程内读取/写入农场模拟，并把状态暴露成 `127.0.0.1:15800` 的 JSON。本技能只负责让 agent 知道怎么装、怎么读、怎么写代码并运行；**不携带 DLL / BepInEx / 游戏文件，也不启动游戏**。

## 包内容

```text
farmer-bridge/
├─ SKILL.md                 触发、前置检查、端点表、主循环
├─ README.md                本文件
├─ scripts/farmer.py        客户端（Python 标准库，无第三方依赖）
├─ references/
│  ├─ API.md                端点与字段
│  └─ INSTALL.md            BepInEx + DLL 安装与排错
├─ examples/
│  ├─ inspect_state.py      读 state / grid / tech
│  └─ run_code.py           写代码并运行
├─ LICENSE                  MIT（dhd）
├─ AI-DISCLOSURE.md
└─ SOURCE.md                上游对应 / 版本 / 未验证项
```

## 前置条件

- **Windows**（BepInEx + Unity x64）；
- 正版游戏 *The Farmer Was Replaced*，用户自备；
- **BepInEx 5.4.23.6 x64**，用户自备，不随包分发；
- `FarmerBridge.dll` 放进 `<游戏目录>\BepInEx\plugins\`；
- Python 3.9+（客户端只用标准库）。

## 安装

1. 退出游戏；
2. 把 BepInEx 5.4.23.6 x64 解压到游戏根目录（与 `TheFarmerWasReplaced.exe` 同级）；
3. 把 `FarmerBridge.dll` 放到 `<游戏目录>\BepInEx\plugins\`；
4. 启动游戏，`<游戏目录>\BepInEx\LogOutput.log` 出现：
   ```text
   FarmerBridge listening on 127.0.0.1:15800
   ```
5. 验证：
   ```powershell
   python scripts\farmer.py state
   ```

详细步骤、卸载与排错见 `references/INSTALL.md`。

### 可选：协助安装（需用户明确同意）

如果游戏和 BepInEx 5.4.23.6 已装、只是 `FarmerBridge.dll` 没装，agent 可以在**用户明确同意**后：

1. 取 `https://api.github.com/repos/dhd78/aigame-plugins/releases/latest` 的资产清单；
2. 下载 `farmer-bridge-v*.zip` + 同一 Release 的 `SHA256SUMS.txt`；
3. 校验 zip 哈希，不符立即停止；
4. 只从 zip 取出 `FarmerBridge.dll`，放到 `<游戏目录>\BepInEx\plugins\`；
5. 请用户重启游戏。

**只装 DLL，不装 BepInEx、不装游戏本体**；用户不同意时只给 Release 链接，不下载、不写文件。详见 `SKILL.md` 的「桥没装时（协助安装）」。

## 快速开始

```powershell
# 1. 健康检查
Invoke-RestMethod http://127.0.0.1:15800/health

# 2. 读状态
python scripts\farmer.py state
python scripts\farmer.py grid --x 0 --y 0 --w 8 --h 8

# 3. 写代码并运行
python scripts\farmer.py code "do_a_flip()" --name main
python scripts\farmer.py run --name main
python scripts\farmer.py output
```

## 端点（摘要）

读：`/health` `/state` `/grid` `/drones` `/items` `/unlocks` `/tech` `/doc` `/files` `/execution` `/output`

写/执行：`/file` `/code` `/run` `/stop` `/step` `/buy` `/save` `/load` `/start`

完整字段见 `references/API.md`。

## 限制

- 只支持 Windows；
- 游戏更新后类型/字段可能变化，桥可能失效；
- `/save` 异步，不等待磁盘完成；
- `/load` 会重建 sim 和代码窗口；
- `/code`、`/run`、`/buy`、`/save` 会改游戏状态/存档，执行前请用户确认；
- 只监听 `127.0.0.1`，**无鉴权，不要暴露到公网/局域网**；
- 调试写接口默认关闭（`FARMERBRIDGE_DEBUG=1` 才开）；本技能不使用、不介绍。

## 许可

MIT，见 `LICENSE`（Copyright (c) 2026 dhd）。BepInEx 是独立项目，不在本包内。

## English

A Windows-only skill for *The Farmer Was Replaced*. The game-side BepInEx plugin `FarmerBridge.dll` (installed by the user) exposes the farm state over `127.0.0.1:15800`; this skill covers installation checks, reading state/grid/tech, writing code to a file page, running it, and reading output.

**Requirements**: Windows, the game, BepInEx 5.4.23.6 x64 (not bundled), and the plugin DLL placed in `<game>\BepInEx\plugins\`. Python 3.9+ for the client.

**Install**: install BepInEx, copy `FarmerBridge.dll` into `BepInEx\plugins\`, start the game, verify the log line `FarmerBridge listening on 127.0.0.1:15800`, then `python scripts\farmer.py state`.

**Assisted install (opt-in)**: if the game and BepInEx are already installed but the DLL is missing, the agent may — only after explicit user consent — fetch the latest `farmer-bridge-v*.zip` and `SHA256SUMS.txt` from the GitHub release, verify the hash, and copy only `FarmerBridge.dll` into `BepInEx\plugins\`. It never downloads BepInEx or the game; without consent it only prints the release URL.

**Links**: endpoint reference in `references/API.md`; install/troubleshooting in `references/INSTALL.md`.

**Limits**: Windows only; game updates may change types/fields; `/save` is asynchronous; writes go to memory and only `/save` touches disk; loopback only, no authentication — do not expose the port. Debug write endpoints are off unless `FARMERBRIDGE_DEBUG=1`; this skill does not use them.

**License**: MIT; BepInEx is a separate project and is not bundled.
