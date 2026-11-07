# Senren Banka Read-Only Bridge v3.2

《千恋＊万花》（Senren * Banka，KiriKiri2）的只读文本桥源码。

它把一个 x86 DLL 注入游戏进程，在 TJS Timer 事件里读取 KAG 历史层，
通过本机 HTTP 提供当前台词、说话人、打字态和推进接口。

## 包内容

```text
senren-bridge-v3.2/
  src/
    senren_bridge_v3.cpp
    injector.cpp
  sdk/
    tp_stub.h
    tp_stub.cpp
    LICENSE-KiriKiri.txt
  docs/
    USAGE.md
    THIRD_PARTY_NOTICES.md
  examples/
    read_state.py
  build.bat
  LICENSE
  SECURITY.md
  README.md
  SHA256SUMS.txt
```

## 构建

需要 Visual Studio x86 工具链：

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

## 使用

```powershell
$game = Get-Process SenrenBanka | Select-Object -First 1
.\injector.exe $game.Id .\senren_bridge_v3.2.dll
Invoke-RestMethod http://127.0.0.1:15528/health
Invoke-RestMethod http://127.0.0.1:15528/state
Invoke-RestMethod -Method Post http://127.0.0.1:15528/advance
```

`/health`：

```json
{"ok":true,"version":"3.2","port":15528}
```

`/state` 示例（合成文本）：

```json
{
  "ok": true,
  "text": "示例台词。\n",
  "author": "示例角色",
  "choices": [],
  "typing": false,
  "can_advance": true,
  "scene": "",
  "timestamp": 1794036403000
}
```

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 版本和端口 |
| GET | `/state` | text / author / typing / can_advance |
| POST | `/advance` | 客户区中心 75% 高点击 |
| GET | `/backlog` | 最多 200 条文本变化 |
| POST | `/choose` | 固定返回 `choose-unavailable` |

## 实现概要

```text
注入 DLL
  → TVPInitImportStub(textrender.dll + 0x33950)
  → TVPAddContinuousEventHook
  → 第一帧执行一次 TJS，创建 Timer(200ms)
  → Timer 读 kag.historyLayer 最后一条 + kag.clickWaiting
  → 写 global.__wlState
  → C++ 连续回调只 PropGet __wlState
  → HTTP 线程只读 C++ 缓存
```

## 已知限制

- 一个进程只注入一个桥；
- 游戏窗口不要最小化；最小化时桥会尝试 `SW_RESTORE`；
- `/choose` 未实现，选项请手动/OCR；
- `scene` 基本为空；
- 只支持 32 位 `SenrenBanka.exe`；
- `textrender.dll + 0x33950` 是版本相关偏移，换版本需重新确认；
- 小时级长跑尚无数据。

## 安全

HTTP 只绑 `127.0.0.1`，无鉴权。详见 [SECURITY.md](SECURITY.md)。

## 许可

- `src/` 与 `injector.cpp`：MIT，见 [LICENSE](LICENSE)；
- `sdk/`：KiriKiri2 作者所有，按 [sdk/LICENSE-KiriKiri.txt](sdk/LICENSE-KiriKiri.txt) 分发。
