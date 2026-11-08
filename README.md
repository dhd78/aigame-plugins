# AI Game Plugins

Bridges and tools that let AI agents read and act inside single-player games. Each plugin lives in its own directory with its own README, license and third-party notices.

## Plugins

| Directory | Game | What it does |
| --- | --- | --- |
| [`pvz-ai-play`](pvz-ai-play/) | Plants vs. Zombies (PvZ1) 1.0.0.1051 | Local HTTP bridge: reads the board, plants/shovels, picks seeds and starts a level. No vision, no OCR, no mouse control |
| [`千恋万花读取文本插件`](千恋万花读取文本插件/) | Senren * Banka | Read-only text bridge: injects into the x86 game process, reads the current KAG history line, exposes it on `127.0.0.1:15528` |

Each plugin's README states the exact game build it was verified against and how to check your own copy.

## Layout

```text
ai-game-plugins/
  pvz-ai-play/
    AGENTS.md        agent-facing manual
    API.md           endpoint and field reference
    docs/            install, patches, design notes
    src/             bridge source
    examples/        reference agent loop
    scripts/         smoke test
    LICENSE          MIT (14-软件开发师·续灯 and dhd)
    THIRD_PARTY_NOTICES.md

  千恋万花读取文本插件/
    src/             bridge + injector source
    sdk/             KiriKiri SDK stubs + license
    docs/            usage and third-party notices
    examples/        minimal Python client
    build.bat        Visual Studio x86 build
    LICENSE          MIT for the bridge/injector
    README.md
    SECURITY.md
```

## License

Each subdirectory carries its own license:

- plugin source: MIT (see that plugin's `LICENSE`);
- third-party dependencies keep their own licenses (`pvztools` MIT, KiriKiri2 license);
- no game assets, scripts or archives are included in this repository.
