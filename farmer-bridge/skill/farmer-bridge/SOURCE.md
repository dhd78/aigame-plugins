# 来源与版本对应

## 上游

| 项 | 值 |
| --- | --- |
| 插件 | `FarmerBridge` 0.1.3+（本包按 0.1.3 编写；0.1.4 兼容） |
| 干净目录 | `仓库/发布/farmer-bridge-0.1.3-clean/` |
| 上游 zip | `仓库/发布/farmer-bridge-v0.1.3.zip`（30,056 字节） |
| 上游 zip SHA-256 | `F0EB9825A9C3B5B04AD70CD65AB747D172D251531C3E936D40E4C8749A3C5E21` |
| 插件许可 | MIT，Copyright (c) 2026 dhd |
| 本技能版本 | `0.1.1`（对应插件 0.1.3+） |

## 本包取用 / 改写

| 本包文件 | 来源 | 改动 |
| --- | --- | --- |
| `scripts/farmer.py` | `farmer_client.py` | 去掉调试相关命令；增加连不上桥的可照做报错；`grid` 不传 `depth` 时读地表（原客户端恒传 `-1`） |
| `references/API.md` | `README.md` 的 HTTP API | 去掉调试写接口；补字段说明与示例 |
| `references/INSTALL.md` | `README.md` 安装 + 排错 | 重写为技能侧步骤；v0.1.1 增加协助安装指引 |
| `examples/inspect_state.py` | 新写 | 读 health/state/grid/tech |
| `examples/run_code.py` | 新写（参考 `examples/minimal.py`） | 写代码 → 运行 → 读输出 |
| `SKILL.md` / `README.md` | 新写 | 触发、前置检查、主循环、边界；v0.1.1 增加“协助安装（需用户同意）” |
| `LICENSE` | 上游 `LICENSE` | 原样 |
| `AI-DISCLOSURE.md` | 上游 `AI-DISCLOSURE.md` | 增加技能打包层 |
| `THIRD_PARTY_NOTICES.md` | 新写 | BepInEx 第三方说明 |

## 未随包

- `FarmerBridge.dll`（二进制，用户自装）；
- `FarmerBridge.cs` / `build.ps1` / `.gitignore`（插件源码与构建，归插件仓）；
- `CHANGELOG.md` / `NOTICE.txt`（插件发布物；安装说明在 `INSTALL.md`）；
- BepInEx、游戏本体、存档、素材。

## 验证

- 2026-11-10：游戏安装、BepInEx 5.4.23.6 + FarmerBridge 0.1.3 运行；
- `/health` 返回 `ok=true, version=0.1.3`；
- `/state`、`/grid`、`/tech`、`/files` 返回真实 JSON；
- 客户端 `state` / `grid` 可读；
- 桥停止后客户端给出“游戏没开 / DLL 没装”的可照做报错；
- v0.1.1 协助安装（本地模拟 Release，2026-11-11）：用户同意 → 取 zip + SHA256SUMS → 校验 → 只解出 DLL；哈希不符 → 停止；用户拒绝 → 只打印 Release 地址，无下载/写入；技能 zip 仍无二进制。

## 未验证

- 其他 Windows 版本 / 其他游戏版本；
- 写接口 `/code`、`/run`、`/buy`、`/save` 的实机行为（本次未调用）；
- Claude Code / Cursor 真实 agent 加载（仅目录约定检查）；
- v0.1.1 协助安装的**真实 GitHub 下载**（测试用本地同版本 Release 资产模拟；逻辑与实际资产一致）。

调试写接口默认关闭（`FARMERBRIDGE_DEBUG=1` 才开），本技能不使用、不介绍。
