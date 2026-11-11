# 安装与排错

> 本包**不含** `FarmerBridge.dll`、BepInEx、游戏本体、存档或素材。
> 以下文件由用户从插件发布页自行取得。

## 前置

| 项 | 要求 |
| --- | --- |
| 系统 | Windows（x64） |
| 游戏 | *The Farmer Was Replaced*，正版，用户自备 |
| BepInEx | **5.4.23.6 x64**（不能是 6.x / x86） |
| 插件 | `FarmerBridge.dll`（与插件版本 `0.1.3` 配套） |
| Python | 3.9+，仅客户端需要 |

## 安装 BepInEx

1. 退出游戏；
2. 从 BepInEx 官方发布页下载 **BepInEx 5.4.23.6 x64**；
3. 解压到游戏根目录，确保与 `TheFarmerWasReplaced.exe` 同级出现：
   ```text
   <游戏目录>\
     TheFarmerWasReplaced.exe
     BepInEx\
     winhttp.dll
     doorstop_config.ini
   ```
4. 启动一次游戏再退出，确认 `BepInEx\LogOutput.log` 生成。

## 安装 FarmerBridge

> 若你同意由 agent 代为安装，见 `SKILL.md` 的「桥没装时（协助安装）」；否则按下面的手动步骤。

1. 把 `FarmerBridge.dll` 复制到：
   ```text
   <游戏目录>\BepInEx\plugins\FarmerBridge.dll
   ```
2. 启动游戏；
3. 打开 `<游戏目录>\BepInEx\LogOutput.log`，应看到：
   ```text
   [Info   :Farmer Bridge] FarmerBridge listening on 127.0.0.1:15800
   ```
4. 验证：
   ```powershell
   Invoke-RestMethod http://127.0.0.1:15800/health
   ```
   期望：
   ```json
   {"ok":true,"bridge":"farmer-bridge","version":"0.1.3","port":15800}
   ```

## 从技能目录运行客户端

```powershell
python scripts\farmer.py state
python scripts\farmer.py grid --x 0 --y 0 --w 8 --h 8
```

客户端只使用 Python 标准库，不需要 `pip install`。

## 卸载

1. 退出游戏；
2. 删除 `<游戏目录>\BepInEx\plugins\FarmerBridge.dll`；
3. 如不再需要 BepInEx，删除 `BepInEx\`、`winhttp.dll`、`doorstop_config.ini`（按 BepInEx 官方卸载说明）。

## 排错

### `/health` 连不上

按顺序判断：

1. **游戏没开**：先启动游戏，进入存档；桥只在游戏进程内运行。
2. **BepInEx 没装/版本不对**：确认 `BepInEx\`、`winhttp.dll`、`doorstop_config.ini` 都在游戏根目录，BepInEx 是 5.4.23.6 x64。
3. **DLL 没放对**：必须是 `<游戏目录>\BepInEx\plugins\FarmerBridge.dll`，不是游戏根目录。
4. **日志看原因**：`BepInEx\LogOutput.log` 里搜 `Farmer Bridge` / `FarmerBridge`；加载失败通常会打印异常。
5. **端口冲突**：确认没有别的进程占用 15800。

### `/health` 通，`/state` 返回 500

通常还在主菜单 / 没进存档。进入存档后再试；或用：

```powershell
python scripts\farmer.py start --save "<存档名>"
```

### `/run` 404

代码页不存在。先建页：

```powershell
python scripts\farmer.py file maze
python scripts\farmer.py code --name maze --file maze.py
python scripts\farmer.py run --name maze
```

### 游戏更新后失效

插件依赖游戏内部类型/字段；游戏更新后可能需要等 `FarmerBridge` 新版本。先看插件发布页的兼容说明。

## 安全

- 桥只监听 `127.0.0.1`，无鉴权；不要做端口转发、不要暴露到局域网/公网；
- `/code`、`/run`、`/buy`、`/save` 会改游戏状态/存档，执行前让用户确认；
- 不要从不可信来源加载 DLL；只使用插件官方发布页的文件。
