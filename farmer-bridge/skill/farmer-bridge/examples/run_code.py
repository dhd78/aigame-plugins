"""Write code to a file page, run it, and print game output.

Run from the skill root:
    python examples/run_code.py --code "do_a_flip()"
    python examples/run_code.py --file my_code.py --name main
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from farmer import api  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", help="inline code")
    parser.add_argument("--file", help="read code from a UTF-8 file")
    parser.add_argument("--name", default="main")
    args = parser.parse_args()

    source = args.code
    if args.file:
        source = Path(args.file).read_text(encoding="utf-8-sig")
    if source is None:
        parser.error("provide --code or --file")

    print("code:", json.dumps(api("/code", "POST", {"file": args.name, "source": source}),
                              ensure_ascii=False))
    print("run:", json.dumps(api("/run", "POST", {"file": args.name}), ensure_ascii=False))
    print("output:", json.dumps(api("/output"), ensure_ascii=False))


if __name__ == "__main__":
    main()
