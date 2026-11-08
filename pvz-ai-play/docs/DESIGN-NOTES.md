# DESIGN NOTES — 内部技术细节（可公开）

这份文档记录桥的实现原理、内存布局和踩过的坑，供维护者参考。
不包含任何个人或内部协作上下文。

---

## 1. 架构

```
┌─────────────┐   HTTP/JSON    ┌──────────────┐   ReadProcessMemory   ┌────────┐
│ 外部智能体   │ ─────────────► │  pvz_server  │ ────────────────────► │ 游戏进程 │
│ (任何语言)   │ ◄───────────── │   :15580     │ ◄──────────────────── │  PvZ1  │
└─────────────┘                └──────────────┘   remote call /        └────────┘
                                                  PostMessage
```

三种操作手段，按可靠性排序：

| 手段 | 用途 | 可靠性 |
| --- | --- | --- |
| **ReadProcessMemory** | 读状态 | 最高，永远可用 |
| **进程内远程调用**（pvztools） | 种植/铲除 | 高，不抢光标 |
| **投递窗口消息**（PostMessage） | 选卡界面点按钮 | 中，游戏只认自己消息循环里的点击 |
| ~~真实鼠标~~ | 备用 | 低：需要前台、会被其他操作干扰 |

实测结论：`PostMessage(WM_MOUSEMOVE + 按下/松开)` 对这版游戏**有效**；
早前误判为无效，是因为用错了验证信号（见第 5 节）。

---

## 2. 内存布局（1.0.0.1051 英文零售版，3,007,800 字节）

### 全局

```text
0x6A9EC0        LawnApp**（全局指针）
app + 0x768     Board*
app + 0x774     SeedChooserScreen*
app + 0x82C     PlayerInfo*（+0x28 = 金钱，显示值 = 内存值 × 10）
app + 0x7FC     game_ui（1 主菜单 2 选卡 3 关卡 5 结算）
```

### Board

```text
board + 0x028   帧计数（判断游戏是否在跑）
board + 0x090   僵尸数组指针        stride 0x15C
board + 0x0AC   植物数组指针        stride 0x14C
board + 0x0B0   植物数组容量
board + 0x11C   场地物品数组指针     stride 0xEC
board + 0x120   场地物品容量
board + 0x144   SeedBank*
board + 0x164   paused
board + 0x5560  阳光
board + 0x554C  场景（0 白天 / 1 夜晚 / 2 池塘 / 3 浓雾 / 4 屋顶）
board + 0x5558  上一帧鼠标 x
board + 0x555C  上一帧鼠标 y
board + 0x60C   冰面左边界 x[6]（默认 800 = 无冰）
board + 0x624   冰面剩余时间[6]（>0 表示该行有冰，约 3000 = 30 秒）
```

### Plant（stride 0x14C）

```text
+0x01C 行      +0x024 类型     +0x028 列
+0x040 血量    +0x044 最大血量
+0x03C state   +0x04C disappear_countdown   +0x050 do_special_countdown
+0x054 state_countdown
```

### SeedPacket（stride 0x50，位于 SeedBank+0x28）

```text
+0x024 cd_elapsed(cs)  +0x028 cd_total(cs)  +0x02C index
+0x030 offset_x        +0x034 type          +0x038 imitater_type
+0x048 usable          +0x049 refreshing    +0x04C times_used
```

### GridItem（stride 0xEC）

```text
+0x008 type   +0x00C state   +0x010 col   +0x014 row   +0x018 counter
+0x020 dead   +0x03C zombie_type   +0x040 seed_type   +0x044 vase_tag
```

类型：`1` 墓碑 / `2` 弹坑 / `3` 梯子 / `4,5` 传送门 / `7` 罐子 / `10` 蜗牛 / `11` 钉耙 / `12` 脑子。

罐子内容：`zombie_type >= 0` → 僵尸罐；否则 `seed_type >= 0` → 植物罐。

### SeedChooserScreen

```text
chooser + 0xD24   已选数量
```

---

## 3. 经济系统的实现

`Board::AddPlant`（远程调用）**不扣阳光、不进冷却**。桥自己补：

1. 成功放置后把 `board + 0x5560` 改成 `sun - cost`；
2. 把种子槽的 `cd_elapsed=0, cd_total=冷却厘秒, usable=0, refreshing=1` 写回——
   游戏自己会跑倒计时，卡片在画面上正常变灰。

这样玩家看到的和正常用卡一致，AI 也不能无限种。

**阳光菇特例**：`AddPlant` 会把 `state_countdown` 初始化成 `1`（应为 `12000`），
下一帧就"长大"。必须在**同一次远程调用内**补写：

```asm
call Board::AddPlant      ; EAX = 新植物指针
mov dword [eax+0x54], 12000
mov dword [eax+0x3C], 23
```

事后补写会出现「逻辑小形态、模型大形态、动画停止」的鬼样子。

---

## 4. 特殊关卡

| 关卡 | 判定 | 规则 |
| --- | --- | --- |
| 传送带 | `seed_bank.conveyor_belt_counter(0x34C) != 0` | 无阳光经济；用一张只清空该格，约 10 秒后游戏补新卡；**不要手动左移补位** |
| 池塘/浓雾 | `scene in {2,3}` | 6 行棋盘，2/3 行是水；水面种陆生植物需荷叶(16) |
| 屋顶 | `scene == 4` | 每格需花盆(33)才能种；花盆逐格检测 |
| 打罐子 | `grid_item type == 7` | 罐子内容可读但不可敲（无接口） |
| 冰面 | `ice_timer[row] > 0` | 冰覆盖范围 `[min_x, 右边界]`，不能种 |

---

## 5. 踩过的坑

1. **投递消息误判为无效**：早期用 `bank_types()` 验证，而选卡界面的种子槽要开局才填，
   永远读到空 → 误判"点击无效"。正确验证信号是 `chooser + 0xD24` 的已选数量。

2. **传送带手动左移补位是错的**：实测游戏不会让后面的卡前移，而是在空位补新卡。
   手动搬字段会破坏 `index`/`usable`，导致卡片灰掉、"重新装填中"、还占位。

3. **静默吞异常**：`except Exception: pass` 让一次常量误删（`NameError`）潜伏很久，
   表现为"传送带读取一直为空"。排查时应先怀疑被吞掉的异常。

4. **底座叠加时校验失败**：用 pvztools 的植物列表校验新植物，在花盆/荷叶上会读不到刚种的那株。
   改用直读 `board+0xAC` 数组（`raw_plants_at`）后解决。

5. **两字节补丁必须整改**：`74 2E → EB 00` 只改首字节会变成 `EB 2E`
   （无条件跳进暂停分支），表现为"冒险模式点不开"。

6. **性能**：每次请求都跑 `tasklist` 查进程要 ~1.5 秒。
   缓存 pid（3 秒 TTL）后 `/state` 从 1665ms 降到 15–20ms。

7. **失焦暂停**：游戏窗口失焦会暂停，冷却不推进、僵尸不动。
   自动化时应保证桌面会话活跃。

8. **D3D 崩溃**：远程桌面断开/锁屏时游戏可能崩在 `d3dim700.dll`，
   属于图形设备丢失，与内存读写无关。

---

## 6. 验证记录（摘要）

- 读状态：阳光、波次、暂停、卡片、植物、僵尸、硬币、场地物品、冰面、水面、花盆、罐子内容
- 种植/铲除：连续数十次成功；扣费与冷却正确
- 选卡+开局：清空 → 选满 → 点开始 → `ui 2→3`
- 特殊关卡：传送带（消耗/补货）、池塘（荷叶）、屋顶（花盆）、冰面、墓碑吞噬者、气球僵尸
- 未验证：通关结算自动衔接、小游戏/解谜完整玩法、小时级长跑
