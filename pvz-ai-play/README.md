# pvz-ai-play — PvZ1 automation bridge for AI agents

A local HTTP bridge that turns *Plants vs. Zombies* (PvZ1) into a JSON state machine: an AI agent reads the board, plants, shovels, picks seeds and starts a level — no screenshots, no OCR, no mouse control.

> **New to this repo? Read [`AGENTS.md`](AGENTS.md) first.** It is written for AI agents: mental model, main loop, word-for-word `409` handling, special-level rules, and a minimal runnable example.

## Supported game

| Item | Value |
| --- | --- |
| Game | *Plants vs. Zombies* (2009) |
| Version | **1.0.0.1051**, English (US) retail build |
| Executable | `PlantsVsZombies.exe`, 3,007,800 bytes |
| Original exe SHA-256 | `678016E417CD55F1F19D7EABB6F2B7E6B87146BE107DB1179A61985078004F7A` |
| Verified (patched) exe SHA-256 | `8DC06FE8E243D8CEF35FBF0D60F6FC1504F1FB549ABD0CC9359C5B76F1110246` — the two optional patches in [`docs/PATCHES.md`](docs/PATCHES.md) were applied to the build used for testing |
| Other versions | Not supported — memory offsets are specific to 1.0.0.1051 (GOTY 1.2.0.1096 does **not** work) |

Note on language: the verified executable is the English retail build, but the bridge's plant/zombie names and most messages are **Chinese** (`向日葵`, `豌豆射手`, …) because they come from mapping tables in the bridge, not from game resources. Use those names in `POST /plant` and `POST /pick`. Chinese and other localised builds are untested.

`/state` also includes `version`, which is `pvztools`' profile id (`1_0_0_1051_en`) rather than a value read from the game.

## Runtime

| Item | Requirement |
| --- | --- |
| OS | Windows (uses `ctypes` + Win32 API) |
| Python | 3.9+ (3.10 / 3.11 tested) |
| Dependency | [`pvztools`](https://pypi.org/project/pvztools/) >= 0.2.0 (MIT) |

## Quick start

```powershell
pip install pvztools
python src\pvz_server.py 15580
python scripts\smoke_test.py
```

`smoke_test.py` checks `/health` and the `/state` shape without requiring a specific level.

If pip cannot reach PyPI, see [`docs/INSTALL.md`](docs/INSTALL.md) for the offline wheel / `PVZTOOLS_VENDOR` route.

## API

All endpoints are `http://127.0.0.1:<port>` (default `15580`) and return JSON. Coordinates are **0-based**: rows `0..4` (rows `0..5` on pool/fog levels), columns `0..8`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | `{"ok":true,"service":"pvz-bridge","port":15580}` |
| GET | `/state` | Full board: sun, seeds, plants, zombies, obstacles, water, pots, ice, vases, conveyor belt |
| POST | `/plant` | `{"row":1,"col":8,"plant":"向日葵"}` |
| POST | `/shovel` | `{"row":1,"col":8}` |
| POST | `/pick` | Choose seeds on the seed-chooser screen |
| POST | `/start` | Click "Let's Rock!" and wait for the level |
| POST | `/continue` | Experimental; coordinates not calibrated |

Full field reference and every `409 reason` (and what to do about it) are in [`API.md`](API.md) and [`AGENTS.md`](AGENTS.md). Short version: **do not retry a 409 blindly — switch card, cell, or wait according to `reason`.**

## How it works

- **Read state**: `ReadProcessMemory` on the running `PlantsVsZombies.exe`. No injection, no overlay, no screenshot.
- **Plant / shovel**: `pvztools` performs a remote call into the game process, so the game runs its own `AddPlant` / removal logic.
- **Pick / start**: window messages (`WM_MOUSEMOVE` + button down/up), so the game does not need focus.
- **Write-back**: the remote call does not charge sun or start cooldowns, so the bridge writes back a small amount of gameplay state — the board's sun value, seed-packet cooldown fields (so the card UI greys out correctly), and a few plant-initialisation fields after planting (for example the Sun-shroom's small form). It does not modify the executable (the optional patches are a separate step), does not read or write save files, and does not target any anti-cheat.
- The bridge only listens on `127.0.0.1`.

Deeper notes on memory layout and the pitfalls behind these choices are in [`docs/DESIGN-NOTES.md`](docs/DESIGN-NOTES.md).

## Special levels

Verified behaviour and the exact `409`/reason mapping are in [`AGENTS.md`](AGENTS.md); the field reference is in [`API.md`](API.md):

- conveyor-belt levels (no sun economy; cards consumed from `belt`)
- pool / fog (lily pads required)
- roof (flower pots required)
- ice from Zomboni (cannot plant)
- vasebreaker (vase contents readable, not breakable through the API yet)
- balloon zombies (`flying: true`; ground shooters cannot hit them)

## Repository layout

```text
pvz-ai-play/
  AGENTS.md                  agent-facing manual (read this first)
  API.md                     endpoint and field reference
  docs/INSTALL.md            install, run, troubleshooting
  docs/PATCHES.md            optional exe patches (auto-collect, background running)
  docs/DESIGN-NOTES.md       memory layout, operation methods, pitfalls
  src/pvz_server.py          the bridge (single file)
  examples/pvz_agent_demo.py reference agent loop
  scripts/smoke_test.py      /health and /state checks
  requirements.txt
  LICENSE                    MIT (14-软件开发师·续灯 and dhd)
  THIRD_PARTY_NOTICES.md     pvztools MIT notice
```

## Known limitations

- `/continue` (level-complete → next level) is experimental and not calibrated; advance the results screen manually.
- Vasebreaker: vase contents are readable, but there is no "smash vase" endpoint.
- `scene` is a coarse code; the fine-grained level type is not exposed.
- Only one bridge instance at a time (pvztools holds a process lock).
- No long-run (hour-scale) testing yet.
- Chinese names are hard-coded; an English name mapping is not provided.

## License

- Bridge code (`src/pvz_server.py`, `examples/`, `scripts/`): **MIT** — see [`LICENSE`](LICENSE). Copyright 14-软件开发师·续灯 and dhd (<https://github.com/dhd78>).
- `pvztools`: MIT, Copyright Blue Rose — see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
- No game files are included in this repository.
