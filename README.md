# AI Game Plugins

Source-only bridges and tools for games. Each plugin lives in its own directory with its own README, license and third-party notices.

## Plugins

| Directory | Game | What it does |
| --- | --- | --- |
| [`千恋万花读取文本插件`](千恋万花读取文本插件/) | Senren * Banka | Read-only text bridge: injects into the x86 game process, reads the current KAG history line, exposes it on `127.0.0.1:15528` |

## Layout

```text
ai-game-plugins/
  千恋万花读取文本插件/
    src/          bridge + injector source
    sdk/          KiriKiri SDK stubs + license
    docs/         usage and third-party notices
    examples/     minimal Python client
    build.bat     Visual Studio x86 build
    LICENSE       MIT for the bridge/injector
    README.md
    SECURITY.md
```

## License

Each subdirectory carries its own license:

- bridge/injector source: MIT (see the plugin's `LICENSE`);
- KiriKiri SDK: KiriKiri2 license, included in `sdk/LICENSE-KiriKiri.txt`;
- no game assets, scripts or archives are included in this repository.
