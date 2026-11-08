# Optional exe patches

The bridge works **without** these patches. They only change two conveniences:

1. sun and coins are collected automatically;
2. the game keeps running while its window is not focused.

Both patches modify `PlantsVsZombies.exe` directly, so **back up the file first**.

```powershell
Copy-Item PlantsVsZombies.exe PlantsVsZombies.exe.orig
```

Target build: **English (US) retail 1.0.0.1051**, `PlantsVsZombies.exe`, 3,007,800 bytes.
The byte positions below were read back from this build; other builds will not match.
On this build, file offsets and RVAs are the same.

---

## Patch 1 — auto-collect sun and coins

```text
file offset 0x3158F:  75 → EB      (jne → jmp; skip the "needs a click" branch)
```

Bytes around the site (original → patched):

```text
original:  15 80 7b 50 00 75 08 53 e8 29
patched:   15 80 7b 50 00 eb 08 53 e8 29
```

Effect: sun and coins go straight into the bank without clicking.

## Patch 2 — keep running when unfocused

```text
file offset 0x14EBA8:  74 → EB
file offset 0x14EBA9:  2E → 00
```

Bytes around the site (original → patched):

```text
original:  d2 04 00 00 74 2e 80 be 31 04
patched:   d2 04 00 00 eb 00 80 be 31 04
```

Effect: losing window focus no longer pauses the game.

> **Both bytes of patch 2 must be changed together.** Changing only the first byte
> produces `EB 2E`, which jumps into the pause branch: adventure mode will not
> open and the game looks broken.

---

## Verify your build

```powershell
Get-FileHash PlantsVsZombies.exe -Algorithm SHA256
```

| State | SHA-256 |
| --- | --- |
| Original, unpatched 1.0.0.1051 retail (3,007,800 bytes) | `678016E417CD55F1F19D7EABB6F2B7E6B87146BE107DB1179A61985078004F7A` |
| Patched build used for verification | `8DC06FE8E243D8CEF35FBF0D60F6FC1504F1FB549ABD0CC9359C5B76F1110246` |

Both hashes were checked against the actual files; the two builds differ in exactly the three patched bytes.

## Restore

```powershell
Copy-Item PlantsVsZombies.exe.orig PlantsVsZombies.exe -Force
```

## Why not a memory patch

Patching instructions at runtime is possible, but it means handling page protection,
restoring on exit, and cleaning up after crashes, and it is more likely to attract
anti-cheat/AV attention. A file patch is simpler and permanent, at the cost of
restarting the game.

The bridge and the patches are decoupled: delete the patches and the bridge still
works, you just have to click sun yourself.
