from __future__ import annotations

import pathlib
import sys

FORBIDDEN = (chr(35), chr(34) * 3, chr(39) * 3)
SKIP_DIRS = ("repos",)


def iter_targets(root: pathlib.Path):
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent
    bad = 0
    checked = 0
    for path in sorted(iter_targets(root)):
        checked += 1
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for token in FORBIDDEN:
                if token in line:
                    print("BAD " + str(path.relative_to(root)) + ":" + str(index) + " " + repr(line))
                    bad += 1
    if bad:
        print("PURITY_FAIL " + str(bad) + " in " + str(checked) + " files")
        return 1
    print("PURITY_OK " + str(checked) + " files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
