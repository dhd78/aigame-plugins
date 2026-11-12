# 安装与运行

## 支持环境

| 项 | 要求 |
| --- | --- |
| 系统 | **Windows**（桥用了 `ctypes` + Win32 API，不支持 Linux/macOS） |
| Python | 3.9+（3.10/3.11 实测可用） |
| 游戏 | 《植物大战僵尸》**1.0.0.1051**（内存偏移针对这版；GOTY 1.2.0.1096 不适用）|
| 语言 | 测试安装为中文文本包（`properties/LawnStrings.txt`，GBK）；exe 本身是英文 build。内存偏移与文本语言无关 |
| 依赖 | [`pvztools`](https://pypi.org/project/pvztools/) 0.2.0+ |

## 一、装依赖

```bash
pip install pvztools
```

如果 pip 报 SSL/OpenSSL 错误（本机遇到过），用离线方式：

```bash
# 1) 从 PyPI 下载 wheel
#    https://pypi.org/project/pvztools/#files
# 2) 解压到任意目录，例如 ./vendor
python -c "import zipfile; zipfile.ZipFile('pvztools-0.2.0-py3-none-any.whl').extractall('./vendor')"
```

然后任选一种方式让桥找到它：

```bash
# 方式 A：环境变量指向 vendor 目录
set PVZTOOLS_VENDOR=<path>\vendor

# 方式 B：把解压出来的 pvztools/ 目录整个放到 pvz_server.py 同级（桥会自动找 ./vendor）
```

## 二、启动游戏

正常启动 `PlantsVsZombies.exe`，进到关卡内或选卡界面都行。

## 三、启动桥

```bash
python pvz_server.py 15580
```

看到这一行就成功了：

```
pvz-bridge listening on http://127.0.0.1:15580
```

验证：

```bash
curl http://127.0.0.1:15580/health
curl http://127.0.0.1:15580/state
```

## 四、跑示例

```bash
python pvz_agent_demo.py 60
```

（会驱动游戏自动选卡、种植物，跑 60 秒）

## 五、常见启动问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `ModuleNotFoundError: pvztools` | 依赖没装/路径没设 | 见第一节 |
| `attach` 报 `ControllerBusy` | 已有一个 pvztools 实例（比如另一个桥） | 杀掉多余的 python 进程 |
| `/state` 返回 500 | 游戏没开 / 版本不对 | 确认进程名 `PlantsVsZombies.exe` 且版本 1.0.0.1051 |
| `GET /state` 很慢（>1s） | 早期版本每次请求都查进程 | 本包已缓存 pid，正常 15–20ms |

## 六、可选：游戏补丁

见 `PATCHES.md`。**不改 exe 也能完整使用桥**，补丁只是让阳光/银币自动收集、以及后台运行。
