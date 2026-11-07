# 使用说明（v3.2）

## 1. 是什么

`senren_bridge_v3.2.dll` 是《千恋＊万花》KiriKiri2 的只读文本桥：

- 注入 32 位 `SenrenBanka.exe`；
- 从 KAG 历史层读当前台词/说话人；
- 本机 `127.0.0.1:15528` 提供 HTTP；
- 不 hook 绘制、不替换窗口过程、不改游戏文件。

## 2. 构建

需要 Visual Studio x86 工具链。

```bat
call "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars32.bat"

cl /nologo /LD /MT /O2 /std:c++17 /EHsc ^
   /I sdk ^
   src\senren_bridge_v3.cpp sdk\tp_stub.cpp ^
   /link ws2_32.lib user32.lib ^
   /Fe:senren_bridge_v3.2.dll
```

注入器：

```bat
cl /nologo /MT /O2 src\injector.cpp /Fe:injector.exe
```

要求：

- x86；
- `/MT`；
- 不引入额外 VC 运行库依赖。

## 3. 运行

### 3.1 启动游戏

正常启动，进入标题画面。

### 3.2 找 PID

```powershell
Get-Process SenrenBanka | Select-Object Id, MainWindowTitle
```

### 3.3 注入一次

```powershell
.\injector.exe <PID> .\senren_bridge_v3.2.dll
```

路径有空格时用引号。

### 3.4 健康检查

```powershell
Invoke-RestMethod http://127.0.0.1:15528/health
```

期望：

```json
{"ok":true,"version":"3.2","port":15528}
```

## 4. `/state`

```http
GET http://127.0.0.1:15528/state
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `ok` | bool | 请求成功 |
| `text` | string | 当前中文台词，可能带换行 |
| `author` | string | 说话人；旁白为空 |
| `typing` | bool | true = 还在逐字显示 |
| `can_advance` | bool | true = 已打完，可推进 |
| `choices` | array | v3.2 始终为 `[]` |
| `scene` | string | v3.2 基本为空 |
| `timestamp` | number | 毫秒时间戳 |

合成示例：

```json
{
  "ok": true,
  "text": "示例台词。\n",
  "author": "示例角色",
  "choices": [],
  "typing": false,
  "can_advance": true
}
```

读取建议：

- 每 300–500ms 轮询一次；
- 用 `(author, text)` 判断换行；
- `typing=true` 时文本可能还在变，等 `false` 再消费；
- 稳定源是历史层最后一条，不是 `_currentText`。

## 5. `/advance`

```http
POST http://127.0.0.1:15528/advance
Content-Type: application/json

{}
```

行为：

- 找 `TVPMainWindow`；
- 最小化时先 `SW_RESTORE`；
- 在客户区中心、75% 高度发鼠标移动/按下/抬起；
- 使用 `PostMessage`，不要求游戏在前台。

返回：

```json
{"ok":true,"attempted":true,"foreground":false,"client":[960,863],"client_size":[1920,1080]}
```

注意：

- 选项画面不要用 `/advance`；
- 串行调用。

## 6. `/backlog`

```http
GET http://127.0.0.1:15528/backlog
```

```json
{"ok":true,"entries":["示例第一句","示例第二句"]}
```

最多 200 条，进程重启后清空。

## 7. `/choose`

v3.2 不实现选项点击，固定返回：

```json
{"ok":false,"error":"choose-unavailable"}
```

选项请手动点或 OCR 坐标点。

## 8. 最小 Python 客户端

```python
import json
import urllib.request

BASE = "http://127.0.0.1:15528"

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))

def post(path, body=None):
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))

if __name__ == "__main__":
    s = get("/state")
    print(s.get("author"), s.get("text"))
    if s.get("can_advance"):
        post("/advance")
```

完整示例见 `examples/read_state.py`。

## 9. 代码结构

```text
senren_bridge_v3.cpp
  DllMain
    → initThread
      → 找 textrender.dll
      → 读 +0x33950 的 iTVPFunctionExporter*
      → TVPInitImportStub
      → TVPAddContinuousEventHook
      → serverThread

  OnContinuousCallback
    → 第一帧执行一次 TJS，创建 Timer(200ms)
    → 后续只 PropGet global.__wlState

  Timer（TJS 事件）
    → kag.historyLayer 最后一条 text/name
    → kag.clickWaiting
    → global.__wlState

  serverThread
    → /health /state /advance /backlog
    → socket 5 秒超时
```

## 10. 版本/偏移

`textrender.dll + 0x33950` 是当前验证版本的 exporter 指针偏移。

换游戏版本后：

1. 先注入空探针，确认能拿到 exporter；
2. 不行就用 IDA/x64dbg 找 `TVPInitImportStub` 调用点；
3. 不要假设偏移永远不变。

找不到 `textrender`、exporter 为空、stub 初始化失败时，v3.2 只写日志并退出，不继续挂 hook。

## 11. 已知限制

- 一个进程只注入一个桥；
- 不要和旧版 15528/15529/15533 叠；
- 窗口最小化时 v3.2 会恢复窗口；
- `choices` / `scene` 未完成；
- 选项画面必须手动/OCR；
- 不同游戏版本字段可能不同。

## 12. 排错

### 15528 没监听

```text
%TEMP%\senren-read-bridge.log
```

常见：

- `no textrender`：注入太早/进程不对；
- `no exporter`：偏移不对；
- `bind failed`：端口被占；
- `stub failed`：TJS 导入失败。

### `/state` 一直空

- 是否还在标题页；
- 是否注入到了别的进程；
- 是否旧桥占着 15528；
- 是否游戏版本不同。

### 点击无效

- 窗口是否最小化；
- 是否在选项画面；
- 是否把消息发到了错误的窗口；
- 是否多个桥同时点。

### 慢连接

每个连接有 5 秒 `SO_RCVTIMEO` / `SO_SNDTIMEO`，只连不发的客户端最多占用 5 秒。

### 崩溃/卡死

```text
%TEMP%\senren-read-bridge.log
%LOCALAPPDATA%\CrashDumps\SenrenBanka.exe.<pid>.dmp
```

## 13. 安全

HTTP 只绑 `127.0.0.1`，无鉴权。详见 `SECURITY.md`。

## 14. 许可

- `src/` 与 `injector.cpp`：MIT；
- `sdk/`：KiriKiri2 作者所有，见 `sdk/LICENSE-KiriKiri.txt`。
