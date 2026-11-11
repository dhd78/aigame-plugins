# AI 参与声明 / AI Disclosure

## 中文

- **插件设计与实现**：AI 助手「榫卯」（07-插件制作师）；
- **技能打包、脱敏与跨 agent 适配**：AI 助手「缄印」（17-打包专家）；
- **实际发布者**：dhd（<https://github.com/dhd78>）。

本技能包**不包含** `FarmerBridge.dll`、BepInEx、游戏本体、存档或素材；DLL 与 BepInEx 由用户自行安装。客户端基于上游 `farmer_client.py`，仅做错误文案与 `grid` 深度参数适配。

v0.1.1 起，技能可在**用户明确同意**后，从 `dhd78/aigame-plugins` 的 GitHub Release 下载插件 zip 与 `SHA256SUMS.txt`，校验哈希后**只取** `FarmerBridge.dll`；不同意时只打印 Release 地址，不下载、不写文件。技能不自动下载 BepInEx 或游戏本体。

测试：2026-11-10 在 Windows 11、游戏已安装、插件 0.1.3 运行的情况下，验证 `/health`、`/state`、`/grid`、`/tech`、`/files` 与客户端；**未调用** `/code`、`/run`、`/buy`、`/save` 等写接口。2026-11-11 用本地同版本 Release 资产模拟协助安装：同意 / 拒绝 / 哈希不符三条路径均通过。

本声明不改变 MIT 许可的效力。

## English

- **Plugin design and implementation**: AI assistant "榫卯" (07, plugin maker).
- **Skill packaging, redaction and cross-agent adaptation**: AI assistant "缄印" (17, packager).
- **Released by**: dhd (<https://github.com/dhd78>).

This skill package does **not** bundle `FarmerBridge.dll`, BepInEx, the game, saves or assets; the user installs the DLL and BepInEx. The client is based on the upstream `farmer_client.py`, with friendlier error messages and a `grid` depth fix.

Since v0.1.1, with **explicit user consent**, the skill may download the plugin zip and `SHA256SUMS.txt` from the `dhd78/aigame-plugins` GitHub release, verify the hash, and copy **only** `FarmerBridge.dll`; without consent it only prints the release URL. It never downloads BepInEx or the game.

Tested on 2026-11-10 on Windows 11 with the game and plugin 0.1.3 running: `/health`, `/state`, `/grid`, `/tech`, `/files` and the client. Write endpoints (`/code`, `/run`, `/buy`, `/save`) were **not** called. On 2026-11-11, assisted install was simulated with local same-version release assets: consent / refusal / hash mismatch all behaved as specified.

This disclosure does not change the MIT license.
