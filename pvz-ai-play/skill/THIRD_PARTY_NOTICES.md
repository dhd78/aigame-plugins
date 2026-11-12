# Third-party notices

## pvztools

- Copyright: Blue Rose
- License: MIT
- Version used: 0.2.0+
- Source: <https://github.com/BlueRoseMike/pvztools>
- PyPI: <https://pypi.org/project/pvztools/>

This project imports `pvztools` at runtime (via `pip install pvztools`, a
vendored directory, or `PVZTOOLS_VENDOR`). It is not bundled in this repository;
install it separately and keep its MIT notice.

The bridge code in `src/pvz_server.py` is released under the MIT license in
`LICENSE`. The bridge uses `pvztools` for process attachment and remote calls;
that dependency stays under its own license.

## Game

No game files are included: no `PlantsVsZombies.exe`, no assets, no save data.
`docs/PATCHES.md` describes two optional byte patches for a specific retail
build; it ships no binary.
