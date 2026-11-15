# Changelog

## 0.1.9 — 2026-11-14

- 放行总结页正常月结按钮 `3processing/panel/result/nextBtn`。
- 继续禁用 `/nextday`、`/load`、`/wish` 以及所有跳过/关闭剧情背景。
- `BepInPlugin` 版本号同步为 `0.1.9`。

## 0.1.8 — 2026-11-14

- `/choose` 增加选择菜单就绪检查；菜单未打开时返回 `choice-not-ready`，不再 `EndChat` 跳过事件。
- 增加 `chat/menu` 与 `ChatSys.menuState` 双重检查。

## 0.1.7 — 2026-11-14

- 禁用 `/nextday`、`/endturn`、`/load`、`/wish`。
- 拒绝聊天背景、父亲心愿背景、心事背景、选项离开按钮等跳过路径。
- `wishChoice` 使用 `ClickMenuChoice` 完成关闭/推进。

## 0.1.5 — 2026-11-14

- 普通台词中的 `&` 不再被误判为选择菜单。
- 识别运行时父亲类型窗口 `TaskSys.faReviewTs`。
- 增加 `stageSummary`、`sureTip`、`choice` 模态守卫。
- 聊天层优先于底层处理页。
- `/click?path` 支持精确定位。

## 0.1.3 — 2026-11-14

- `wishChoice` 不再直接调用 `ChooseWishPerChoice`，避免旧条目残留。
- 补 `fatherWish` 路径检测。

## 0.1.1 — 2026-11-14

- `/state`、`/ui` 增加 `busy`、`modal`、`modalChoices` / `modalButtons`。
- 动作接口增加 busy 守卫。
- 支持 `/uibtn?path` 精确选择。

## 0.1.0 — 2026-11-11

首个可用版本：

- `/health`、`/state`、`/ui`、`/click`
- `/chat`、`/choose`、`/advance`
- `/uibtn`、`/nextday`、`/resnpc`、`/talentinfo`
- 存档解密读取
