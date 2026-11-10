# API 参考

Base URL：`http://127.0.0.1:15800`

- 所有响应为 JSON；
- 只绑定回环地址，**无鉴权**；
- 写接口会改游戏内存；只有 `/save` 写磁盘。

## 读

| 端点 | 参数 | 返回 |
| --- | --- | --- |
| `GET /health` | — | `ok` / `bridge` / `version` / `port` |
| `GET /state` | — | 总览：`ok`、`main`、`ui`、`sim`、`time`、`executing`、`paused`、`farm`、`drones` 等 |
| `GET /grid` | `x`、`y`、`w`、`h`；可选 `depth` | 地表：每格 `x` `y` `z` `entity` `water` `cactus`；地下：`present` `ground` `hardness` `stability` |
| `GET /drones` | — | 无人机 `id` `x` `y` `z` |
| `GET /items` | — | 物品名 → 数量 |
| `GET /unlocks` | — | 已解锁项 |
| `GET /tech` | — | 科技节点：`name` `level` `max` `parent` `cost` `nextCost` `dlc` `installed` |
| `GET /doc` | `page` | 游戏内文档页（如 `docs/scripting/while.md`） |
| `GET /files` | — | 代码文件列表 + 当前页 |
| `GET /execution` | — | 当前是否在执行 / 暂停 |
| `GET /output` | — | 游戏 `print` 输出 |

### `/state` 常用字段

```json
{
  "ok": true,
  "main": true,
  "ui": true,
  "sim": true,
  "time": 4.487,
  "executing": false,
  "paused": false,
  "farm": {
    "mainDroneId": 0,
    "dlc": "None",
    "world": [16, 16],
    "maxUncoveredDepth": 0
  },
  "drones": [{"id": 0, "x": 0, "y": 0, "z": 0}]
}
```

- `time`：游戏内时间；
- `executing` / `paused`：代码是否在跑/暂停；
- `farm.dlc`：启用的 DLC（如 `Mining`；未启用为空串/`None`）；
- `farm.maxUncoveredDepth`：已挖到的最深地下层。

### `/grid`

```text
GET /grid?x=0&y=0&w=8&h=8          # 地表
GET /grid?x=0&y=0&w=8&h=8&depth=16 # 地下层
```

不传 `depth` 时读地表，单元格字段为 `entity` / `water` / `cactus` 等；传 `depth=N` 时读第 N 层地下，字段为 `present` / `ground` / `hardness` / `stability`。

### `/tech` 示例

```json
{
  "name": "speed",
  "level": 1,
  "max": 5,
  "parent": "loops",
  "cost": {"hay": 20},
  "nextCost": {"wood": 20},
  "dlc": "None",
  "installed": true
}
```

## 写 / 执行

| 端点 | Body | 说明 |
| --- | --- | --- |
| `POST /file` | `{"name":"maze"}` | 创建/选择代码页；文件名限字母数字 `_` `-`，≤32 字符 |
| `POST /code` | `{"file":"main","source":"..."}` | 写入代码；`file` 省略时为 `main` |
| `POST /run` | `{"file":"main"}` | 运行代码 |
| `POST /stop` | `{}` | 停止 |
| `POST /step` | `{}` | 单步 |
| `POST /buy` | `{"name":"loops"}` | 按游戏规则购买科技；**扣材料** |
| `POST /save` | `{}` | 存档（异步返回 `queued`，不等待磁盘完成） |
| `POST /load` | `{}` | 读当前存档；重建 sim / 代码窗口 |
| `POST /start` | `{"save":"名字"}` | 加载存档并进入游戏；省略 `save` 用当前存档 |

## 示例

```bash
curl http://127.0.0.1:15800/health
curl http://127.0.0.1:15800/state
curl "http://127.0.0.1:15800/grid?x=0&y=0&w=8&h=8&depth=16"
curl -X POST http://127.0.0.1:15800/code -H "Content-Type: application/json" \
  -d '{"file":"main","source":"do_a_flip()"}'
curl -X POST http://127.0.0.1:15800/run -H "Content-Type: application/json" \
  -d '{"file":"main"}'
curl http://127.0.0.1:15800/output
```

## 错误

- HTTP 非 2xx：响应体里通常有 `error` 或 `ok:false`；
- `/health` 连不上：游戏没开 / DLL 没装（见 `INSTALL.md`）；
- `/state` 500：可能还在主菜单，先进存档；
- `/run` 404：代码页不存在，先 `POST /file`。

## 边界

- 调试写接口默认关闭，只有 `FARMERBRIDGE_DEBUG=1` 才启用；本技能不使用、也不介绍；
- 游戏更新后字段可能变化；本参考对应插件 `0.1.3`；
- 端口只监听 `127.0.0.1`，不要暴露。
