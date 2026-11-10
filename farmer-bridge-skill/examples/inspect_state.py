"""Read bridge health, farm state, grid and tech tree.

Run from the skill root:
    python examples/inspect_state.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from farmer import api  # noqa: E402


def main():
    health = api("/health")
    print("health:", json.dumps(health, ensure_ascii=False))

    state = api("/state")
    farm = state.get("farm", {})
    print("time:", state.get("time"), "executing:", state.get("executing"))
    print("world:", farm.get("world"), "dlc:", farm.get("dlc"),
          "maxDepth:", farm.get("maxUncoveredDepth"))
    print("drones:", len(state.get("drones", [])))

    grid = api("/grid?x=0&y=0&w=4&h=4")
    print("grid cells:", len(grid.get("cells", [])))
    print("first cell:", json.dumps(grid.get("cells", [{}])[0], ensure_ascii=False))

    tech = api("/tech")
    print("tech nodes:", len(tech.get("tech", [])))


if __name__ == "__main__":
    main()
