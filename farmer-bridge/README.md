# FarmerBridge

《编程农场》（The Farmer Was Replaced）的本地内存桥。

通过 BepInEx 在游戏进程内读取/写入 `MainSim`、`Simulation`、`Farm`、
`GridManager`、`Drone`、`CodeWindow`，提供本地 HTTP JSON 接口。

不依赖截图、虚拟鼠标或键盘事件。

> 当前版本：`0.1.1`
>
> 测试环境：Unity `6000.0.43.9905963` + Mono x64 + BepInEx `5.4.23.6`

## 功能

- 读取农场、无人机、地块、物品、解锁、执行状态；
- 读取游戏内文档；
- 按游戏规则购买科技树（`MainSim.UnlockOrUpgrade`，会扣材料）；
- 设置/运行/停止/单步代码；
- 多个独立代码页（`main`、`maze` 等）；
- 读取游戏输出；
- 存档/读档；
- 本地 Python 客户端，无第三方 Python 依赖。

## 安装

### 1. 安装 BepInEx

安装 **BepInEx 5.4.23.6 x64** 到游戏根目录：

```text
<游戏目录>\
  TheFarmerWasReplaced.exe
  BepInEx\
  winhttp.dll
  doorstop_config.ini
```

本项目**不包含** BepInEx 二进制；请从其官方发布页下载。

### 2. 安装插件

把以下文件放到：

```text
<游戏目录>\BepInEx\plugins\FarmerBridge.dll
```

### 3. 启动

启动游戏。日志在：

```text
<游戏目录>\BepInEx\LogOutput.log
```

看到：

```text
FarmerBridge listening on 127.0.0.1:15800
```

即启动成功。

## 客户端

```bash
python farmer_client.py state
python farmer_client.py files
python farmer_client.py file maze
python farmer_client.py code --name maze --file maze.py
python farmer_client.py run --name maze
python farmer_client.py output
python farmer_client.py stop
```

默认代码页是 `main`。

## HTTP API

### 读取

```text
GET /health
GET /state
GET /grid?x=0&y=0&w=8&h=8
GET /drones
GET /items
GET /unlocks
GET /tech
GET /doc?page=docs/scripting/while.md
GET /files
GET /execution
GET /output
```

### 代码文件

```text
POST /file   {"name":"maze"}
```

文件不存在时自动创建。文件名限制为字母、数字、`_`、`-`，最多 32 字符。

### 代码

```text
POST /code   {"file":"main","source":"harvest()"}
POST /run    {"file":"main"}
POST /stop
POST /step
```

`file` 省略时为 `main`。

### 科技树

```text
POST /buy    {"name":"loops"}
```

调用游戏自身的 `MainSim.UnlockOrUpgrade(UnlockSO)`，检查前置并扣除材料。

`/tech` 返回：

```json
{
  "name": "speed",
  "level": 1,
  "max": 5,
  "parent": "loops",
  "cost": {"hay": 20},
  "nextCost": {"wood": 20}
}
```

### 存档

```text
POST /save
POST /load
```

## 实现

```text
BepInEx 5.4.23.6
  └─ FarmerBridge.dll
       ├─ BaseUnityPlugin.Awake
       │    └─ TcpListener 127.0.0.1:15800
       ├─ BaseUnityPlugin.Update
       │    └─ 主线程队列；Unity/Mono 对象操作都在主线程执行
       └─ HTTP 线程
            └─ 入队请求、等待结果、返回 JSON
```

关键对象：

```csharp
MainSim._instance        // private static，反射
MainSim.sim              // private，反射
UISim.Inst
UISim.sim                // private，反射
Simulation.farm
Farm.grid
Farm.drones
Farm.Items
Farm.unlocks             // private，反射
```

代码执行：

```csharp
var cw = workspace.codeWindows["main"];
cw.CodeInput.text = source;
var node = cw.Parse();
main.StartMainExecution(cw, node, false);
```

## 已知限制

1. 游戏更新后类型/字段可能变化，需要重新确认；
2. `/save` 异步返回 `queued`，不等待磁盘完成；
3. `/load` 会重建 sim 和代码窗口；
4. 所有写操作直接改内存，只有 `/save` 写磁盘；
5. HTTP 只绑定 `127.0.0.1`，无鉴权，不要暴露到公网；
6. `set_entity` 的实体名映射仍需细化；

## 构建

需要 .NET Framework 4.x x64 编译器（`csc.exe`）和以下引用：

```text
BepInEx\core\BepInEx.dll
TheFarmerWasReplaced_Data\Managed\Core.dll
TheFarmerWasReplaced_Data\Managed\Utils.dll
TheFarmerWasReplaced_Data\Managed\UnityEngine.dll
TheFarmerWasReplaced_Data\Managed\UnityEngine.CoreModule.dll
TheFarmerWasReplaced_Data\Managed\UnityEngine.UI.dll
System.dll
System.Core.dll
System.Net.dll
netstandard.dll
```

运行：

```powershell
.\build.ps1 -GameDir "<游戏目录>"
```

输出：

```text
dist\FarmerBridge.dll
```

## 第三方

- BepInEx：https://github.com/BepInEx/BepInEx

## 许可证

MIT，见 `LICENSE`。

## English

A local memory bridge for *The Farmer Was Replaced*: a BepInEx plugin exposes the game's `MainSim` / `Simulation` / `Farm` / `GridManager` / `Drone` / `CodeWindow` objects over a loopback HTTP JSON API, so an agent can read the farm and write/run game code without screenshots, virtual mouse or keyboard events.

**Requirements**: Windows, the game itself, and BepInEx 5.4.23.6 (x64) installed by you. BepInEx binaries are not bundled.

**Install**

1. Install BepInEx 5.4.23.6 x64 into the game directory.
2. Copy `FarmerBridge.dll` to `<game>\BepInEx\plugins\`.
3. Start the game; the log shows `FarmerBridge listening on 127.0.0.1:15800`.

**API** (all JSON; loopback only, no authentication)

```text
GET  /health  /state  /grid  /drones  /items  /unlocks  /tech  /doc  /files  /execution  /output
POST /file  /code  /run  /stop  /step  /buy  /save  /load
```

**Client**: `python farmer_client.py state` — no third-party Python packages.

**Limits**: game updates may change types/fields; `/save` is asynchronous; all writes go to memory and only `/save` touches disk; keep the port on loopback.

**License**: MIT.
