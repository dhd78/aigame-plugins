# Changelog

## 0.1.2 — 2026-11-10

- 挖矿 DLC 适配：`/state` 增加 `dlc`、`maxUncoveredDepth`。
- `/grid?depth=N` 支持地下地块读取（`present`、`ground`、`hardness`、`stability`）。
- `/tech` 增加 `dlc`、`installed` 字段。
- 调试接口 `/set_ground` 支持 `depth`。
- 客户端 `grid --depth`。
- 版本号同步到 `0.1.2`。

## 0.1.1 — 2026-11-10

- 调试写接口默认关闭；设置 `FARMERBRIDGE_DEBUG=1` 后才启用 `/add_item`、`/set_drone`、`/set_ground`、`/set_entity`。
- 版本号同步到 `0.1.1`。

## 0.1.0 — 2026-11-10

首个可用版本。

- 内存读取：Farm / Grid / Drone / Items / Unlocks / Execution
- 游戏文档读取
- 科技树读取与按规则购买
- 代码写入、运行、停止、单步
- 多代码页（`/files`, `/file`，`/code` `/run` 支持 `file`）
- 游戏输出读取
- 存档/读档
- Python 客户端

已知问题：

- `set_entity` 的实体名映射仍需细化
- `/save` 异步，不等待磁盘完成
