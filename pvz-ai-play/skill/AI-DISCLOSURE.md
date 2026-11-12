# AI 参与声明 / AI Disclosure

## 中文

- **桥的设计与实现**：由 AI 助手 **14-软件开发师·续灯** 在 DSH 会话中完成；实际创作者 dhd（[dhd78](https://github.com/dhd78)）负责需求、验证与发布决定。
- **打包层**：17-打包专家·缄印（AI），负责技能包结构、SKILL / README、跨 agent 适配、校验与发布候选（v0.1.2 候选，2026-11-12；对齐桥 0.2.0 接口）。
- **LICENSE 只写实际创作者 dhd**；本文件保留实现参与记录，不改变 MIT 许可。
- **本包保留写游戏内存的实现**（阳光扣费、卡片冷却、种植初始化字段），这是业主拍板、12 明码书面转达的例外；不是 17 默认口径。
- **v0.1.2 接口对齐**：同步桥 0.2.0 的小游戏 / 全屏点击 / 新 `/state` 字段；`/debug_click`、`/force_plant` 标为调试，不写入主流程。
- **未验证**：本包未在真实游戏 + `pvztools` 环境实跑；未在真实 Claude Code / Cursor 安装中验证。
- 本声明不改变 MIT 许可的效力。

## English

- The bridge was designed and implemented by the AI assistant **14-软件开发师·续灯** in a DSH session; the actual creator is **dhd** ([dhd78](https://github.com/dhd78)).
- **Packaging layer**: 17-打包专家·缄印 (AI), responsible for skill structure, SKILL / README, cross-agent adaptation, validation and release candidate (v0.1.2 candidate, 2026-11-12; aligned to bridge 0.2.0).
- **LICENSE names the actual creator dhd only**; this file keeps the implementation participation record and does not change the MIT license.
- This package **retains game-memory writes** (sun deduction, seed cooldowns, plant-init fields), an exception approved by the owner and relayed in writing by 12-明码; it is not 17's default policy.
- **v0.1.2 interface alignment**: synced bridge 0.2.0 minigames / fullscreen click / new `/state` fields; `/debug_click` and `/force_plant` are marked debug-only and not part of the main loop.
- **Not verified**: not run against a real game with `pvztools`; not installed in real Claude Code / Cursor.
- This disclosure does not change the MIT license.
