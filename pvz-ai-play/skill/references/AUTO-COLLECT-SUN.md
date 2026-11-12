# 可选 exe 补丁：自动收阳光 / 失焦继续

> 本文件只是**文字说明**；本包不包含 `PlantsVsZombies.exe`、不打补丁、不自动改 exe。
> 数据由 12 明码核对后转达（2026-11-09），数值不要改。

## 适用

- 游戏：*Plants vs. Zombies* 1.0.0.1051 英文零售版；
- 文件：`PlantsVsZombies.exe`，**3,007,800 字节**；
- 原始 SHA-256：`678016E417CD55F1F19D7EABB6F2B7E6B87146BE107DB1179A61985078004F7A`；
- 补丁后 SHA-256：`8DC06FE8E243D8CEF35FBF0D60F6FC1504F1FB549ABD0CC9359C5B76F1110246`。

> 只对这个构建有效；其他版本 / 语言 / GOTY 1.2.0.1096 不保证。文件偏移与 RVA 在此构建上相同。

## 先备份

```powershell
Copy-Item PlantsVsZombies.exe PlantsVsZombies.exe.orig
```

还原：把 `PlantsVsZombies.exe.orig` 拷回 `PlantsVsZombies.exe`。

## 补丁 1：自动收集阳光 / 银币

```text
RVA 0x3158F:  75 → EB      (jne → jmp)
```

作用：跳过“需要点击”分支，阳光 / 银币直接进账。

## 补丁 2：失焦后继续运行（可选）

```text
RVA 0x14EBA8:  74 → EB
RVA 0x14EBA9:  2E → 00
```

⚠ **两个字节必须一起改**；只改首字节会变成 `EB 2E`，冒险模式点不开。

## 与桥的关系

- 补丁与桥**解耦**：不打补丁，桥照样能用，只是要自己点阳光 / 窗口失焦会暂停；
- 本包不检查、不应用、不校验补丁；打完补丁后 exe 的 SHA 会变成上面的“补丁后 SHA”，与本包无关；
- 修改 exe 有风险（崩溃 / 杀软误报 / 存档异常），自行决定并备份；不要分发打过补丁的 exe。
