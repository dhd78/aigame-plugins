# VolcanoBridge 0.1.9

《火山的女儿 / Volcano Princess》的本地内存桥：通过 BepInEx 在游戏进程内读取 UI、剧情与数值，并以 JSON 提供 HTTP 接口。不依赖截图、OCR、虚拟鼠标或键盘事件。

| 项 | 值 |
| --- | --- |
| 版本 | `0.1.9` |
| 游戏 | 火山的女儿 / Volcano Princess |
| 运行时 | Unity 6 Mono |
| 加载器 | BepInEx 5.4.23.6 x64 |
| 端口 | `127.0.0.1:15801` |

## 安装

```text
<游戏目录>/
  BepInEx/
    plugins/
      VolcanoBridge.dll
```

启动游戏后：

```powershell
Invoke-RestMethod http://127.0.0.1:15801/health
# {"ok":true,"bridge":"volcano-bridge","version":"0.1.9","port":15801}
```

## 接口

### 读取

| 端点 | 说明 |
| --- | --- |
| `GET /health` | 桥版本与端口 |
| `GET /state` | turn、coin、energy、stage、month、year、dau、courses、map、chat，以及 `busy` / `modal` |
| `GET /ui` | 当前界面按钮，带完整路径；另含 `busy`、`modal`、`modalButtons` |
| `GET /chat` | 当前对话与选项 |
| `GET /savedata?slot=12` | 读取指定槽位的存档数据 |

`modal` 取值：`chat` / `worryChoice` / `stageSummary` / `sureTip` / `choice` / `fatherWish` / `plan` / 空串。

### 剧情

| 端点 | 说明 |
| --- | --- |
| `GET /advance` | 推进一句台词；普通台词里的 `&` 不会被当成选择菜单 |
| `GET /choose?index=0` | 在真实选择菜单中选一项 |

选择菜单尚未打开时返回：

```json
{"ok":false,"error":"choice-not-ready","retryMs":200}
```

此时对话保持不变，等待后重试即可。

### 点击

| 端点 | 说明 |
| --- | --- |
| `GET /click?index=0` | 按顺序点当前界面的第 N 个可点元素 |
| `GET /click?path=<url-encoded-path>` | 按 `ui.buttons[].path` 精确点击 |
| `GET /uibtn?index=0` | 按顺序点 UI 按钮 |
| `GET /uibtn?path=<url-encoded-path>` | 按 `ui.uibuttons[].path` 精确点击 |

模态窗口内用 `path` 点击更稳定；`index` 只在当前 UI 状态下有效，跨帧请用 `path`。

### 其他

| 端点 | 说明 |
| --- | --- |
| `GET /talentinfo?cell=0/1` | 读取天赋格的详情描述 |
| `GET /resnpc?name=spring14` | 调用地图上的 `MapSys.ClickSelectBtn(name)` 选中 NPC |

## 限制

- 只提供以下月结入口：总结页 `UI/UI/TopShowUi/3processing/panel/result/nextBtn`；
- 以下快捷接口不开放：`/nextday`、`/endturn`、`/load`、`/wish`；
- 以下跳过/关闭剧情的路径被拒绝：`UI/49 TipUi/14Chat/bg`、`UI/UI/36 TopWnd/50 父亲心愿/bg`、`worryChoice/bg`、`4按钮/panel/choice/cells/002leaveBtn`；
- `plan` 打开时 `/nextday` 同样被拒绝，关闭日程按钮仍可用；
- 内存偏移与 UI 路径针对当前游戏构建，游戏更新后需要同步；
- 所有写操作直接改内存，不自动存档；
- 服务只绑定 `127.0.0.1`。

## 构建

需要 .NET Framework 4.x x64 编译器：

```powershell
.\build.ps1 -GameDir '<游戏目录>'
```

输出：

```text
dist/VolcanoBridge.dll
```

## 许可证

MIT，见 `LICENSE`。第三方组件见 `THIRD_PARTY_NOTICES.md`。

## English

VolcanoBridge is a local memory bridge for *Volcano Princess* (火山的女儿). A BepInEx plugin reads UI, dialogue and stats inside the game process and exposes them as JSON over a loopback HTTP API — no screenshots, OCR, mouse or keyboard events.

| Item | Value |
| --- | --- |
| Version | `0.1.9` |
| Runtime | Unity 6 Mono |
| Loader | BepInEx 5.4.23.6 x64 |
| Port | `127.0.0.1:15801` |

**Install**: copy `VolcanoBridge.dll` into `<game>\BepInEx\plugins\`, start the game, then `GET http://127.0.0.1:15801/health`.

**Read**: `/health`, `/state`, `/ui`, `/chat`, `/savedata?slot=N`.

**Story**: `/advance` moves one line; `/choose?index=N` picks an option. When no choice menu is open it returns `{"ok":false,"error":"choice-not-ready","retryMs":200}` and leaves the dialogue unchanged.

**Click**: `/click?index=N`, `/click?path=...`, `/uibtn?index=N`, `/uibtn?path=...`. Prefer `path` inside modal windows; `index` is only valid for the current UI state.

**Other**: `/talentinfo?cell=0/1`, `/resnpc?name=spring14`.

**Limits**: the only month-end button exposed is the summary page's `3processing/panel/result/nextBtn`; `/nextday`, `/endturn`, `/load`, `/wish` and the dialogue-skipping paths are not available. Offsets and UI paths target the current game build; writes go to memory and are not auto-saved; the server binds to `127.0.0.1` only.

**Build**: `.\build.ps1 -GameDir '<game>'` with a .NET Framework 4.x x64 compiler.

**License**: MIT. See `LICENSE` and `THIRD_PARTY_NOTICES.md`.
