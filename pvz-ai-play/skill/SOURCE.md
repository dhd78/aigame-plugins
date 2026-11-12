# 来源与重建

## 上游

| 项 | 值 |
| --- | --- |
| 仓库 | <https://github.com/dhd78/aigame-plugins>（本地 `ai-game-plugins/pvz-ai-play/`） |
| 上游版本 | **`pvz-ai-play` 0.2.0**（minigames + fullscreen） |
| 上游 commit | `efba5b5`（`docs: pvz-ai-play 0.2.0 (minigames + fullscreen)`；本地 `origin/main`） |
| 上游 zip | `仓库/发布/pvz-ai-play-v0.2.0.zip`（59,949 字节） |
| 上游 zip SHA-256 | `0E8855574B18E2D11BFEEC0D6553B26150BA2369F586ACE35D0BB796B809EDFF` |
| Release | <https://github.com/dhd78/aigame-plugins/releases/tag/pvz-ai-play-v0.2.0> |
| 上游许可 | MIT，Copyright (c) 2026 dhd（本包 LICENSE 只写 dhd；实现参与见 `AI-DISCLOSURE.md`） |
| 本包版本 | `0.1.2`（技能 0.1.2 ↔ 桥 0.2.0） |

## 上游文件 SHA-256（0.2.0 zip）

| 文件 | SHA-256 | 本包路径 | 改动 |
| --- | --- | --- | --- |
| `src/pvz_server.py` | `7A2BF53F6125B12E6C15A20AB1E06C6DAA72DCF45C9106E7E3C3E9CA5DF774AF` | `src/pvz_server.py` | 原样 |
| `scripts/smoke_test.py` | `2FA363D38018947A06116A42FD0E6F057CC49DAC9CFE770A324747B527D8E20D` | `scripts/smoke_test.py` | 原样 |
| `requirements.txt` | `2359A9E53D41F2EF502135EA034968158977E59CA4B870ABD8642909A2FDB7EE` | `requirements.txt` | 原样 |
| `AGENTS.md` | `57765AF0DBF06163ACB755858556201AFD072D4A2BC663FA5011AF70E12C4679` | `references/AGENTS.md` | 修正坐标口径（屋顶 0..4 / 池塘 0..5）+ 像素换算；10.8 改用 `/click` |
| `API.md` | `D7F22A9E04CD08062A0B5DCC8DE317CFC196E27796F0E581B5DBB9697331D273` | `references/API.md` | 加坐标/像素换算；`/debug_click`、`/force_plant` 标调试 |
| `docs/DESIGN-NOTES.md` | `330F5AEB0A1D8A0A283737EF80E2C021C7350BAF1C7E4AB8AABC2F0736149853` | `references/DESIGN-NOTES.md` | 原样 |

> 上游 zip 未含 `LICENSE` / `THIRD_PARTY_NOTICES.md`；本包沿用 0.1.1 的 `LICENSE`（dhd）与 `THIRD_PARTY_NOTICES.md`（pvztools MIT）。

## 本包做了什么

- 收录 0.2.0 桥源码（未裁剪），保留全部端点与小游戏；
- `SKILL.md`：加触发词、版本说明、坐标/像素、小游戏分支；
- `references/AGENTS.md` / `API.md`：同步 0.2.0，并修正坐标口径、补像素换算、把调试接口标出；
- `README.md` / `SOURCE.md` / `AI-DISCLOSURE.md`：版本 `0.1.2 ↔ 0.2.0`，补 0.2.0 接口对齐；
- `SHA256SUMS.txt` 重算；zip 仍只含文本 + Python，无二进制。

## 版本对应

| 上游 `pvz-ai-play` | 本包 `pvz-play` | 说明 |
| --- | --- | --- |
| `0.2.0` | `0.1.2` | 同步 0.2.0 全部端点 / 小游戏 / 全屏点击；技能层文档 |
| 后续 0.2.x | `0.1.x` | 跟随上游非破坏改动；桥协议变化再升技能大版本 |

## 打包环境

| 项 | 值 |
| --- | --- |
| 系统 | Windows 11 家庭版中文版，10.0.26200 |
| Python | 3.12.14（打包 / 静态检查；**未安装 pvztools**） |
| 游戏 | `PlantsVsZombies.exe` 3,007,800 字节（本机有；未启动测试） |
| 时区 | Asia/Shanghai |

## 验证记录（v0.1.2 候选）

| 项 | 结果 |
| --- | --- |
| `python -m py_compile src/pvz_server.py` | 通过（不导入 pvztools） |
| 端点表对照 0.2.0 API | 通过：`/health` `/state` `/plant` `/shovel` `/pick` `/start` `/continue` `/click` `/debug_click` `/force_plant` `/recalibrate` `/spin` `/begh_swap` `/twist_rotate` `/break_vase` `/vase_plant` `/next_wave` `/plant_prize` `/belt_compact` |
| 坐标口径 | 屋顶 0..4（5 行）、池塘/浓雾 0..5（6 行）；像素公式已写入 AGENTS/API/SKILL |
| 确定性 zip | 连续两次 SHA 一致 |
| 干净解压（空格 + 中文路径） | 通过 |
| 包内 SHA 逐项匹配 | 通过 |
| 无二进制 | 通过（无 exe / dll / 图片 / pyc） |
| 真实游戏实测 | **未做**：本机无 `pvztools`；17 不擅自装 |
| 真实 agent | **未做**：未在真实 Claude Code / Cursor 安装中验证 |

完整命令与输出见 `厨房/审计/2026-11-12-pvz-play-v0.1.2/`（不随包分发）。
