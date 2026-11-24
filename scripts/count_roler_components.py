"""Estimate the Discord character and component counts of Roler markup messages.

Usage: uv run scripts/count_roler_components.py <file> [<file> ...]

Discord rejects a message over 4000 characters (with Nitro) or over 40 components. The component
count follows Roler's documented rules (https://seria.is-a.dev/roler/):
- Each blank-line-separated block of text is one Text Display. Headings are counted as their own
  Text Display: a layout counted at 36 without that rule was rejected by Discord.
- `[image]`, `[gallery]` (any number of items), `---` and `[separator]` are one component each.
- Buttons on the same or consecutive lines share one Action Row (a blank line starts a new row);
  the row and each button count.
- A `[section]` counts itself, each text line and its accessory.
- `[webhook]` and `[template]` lines aren't components.

Calibration: v1.17.0's main message counts 40 and was accepted; a v1.18.0 draft counting 47 was
rejected. It's still an estimate: when a message is rejected at a lower count, trust Discord.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHAR_LIMIT = 4000
COMPONENT_LIMIT = 40
HEADING = re.compile(r"#{1,3} ")


def count_components(markup: str) -> int:
    count = 0
    in_text = in_gallery = in_section = in_row = False

    for raw_line in markup.splitlines():
        line = raw_line.strip()
        was_in_row, in_row = in_row, False

        if in_gallery:
            in_gallery = line != "[/gallery]"
            continue
        if in_section:
            if line == "[/section]":
                in_section = False
            elif line:
                count += 1
            continue

        if not line or line.startswith(("[webhook", "[template")):
            in_text = False
        elif line == "[gallery]":
            count += 1
            in_gallery, in_text = True, False
        elif line == "[section]":
            count += 1
            in_section, in_text = True, False
        elif line == "---" or line.startswith(("[separator", "[image")):
            count += 1
            in_text = False
        elif line.startswith("[button"):
            count += (0 if was_in_row else 1) + line.count("[button")
            in_text, in_row = False, True
        elif HEADING.match(line):
            count += 1
            in_text = False
        elif not in_text:
            count += 1
            in_text = True

    return count


def main() -> None:
    for path in map(Path, sys.argv[1:]):
        markup = path.read_text(encoding="utf-8")
        chars, components = len(markup), count_components(markup)
        over = [
            name
            for name, value, limit in (
                ("chars", chars, CHAR_LIMIT),
                ("components", components, COMPONENT_LIMIT),
            )
            if value > limit
        ]
        status = f"OVER: {', '.join(over)}" if over else "ok"
        print(f"{path}: {chars} chars, ~{components} components ({status})")


if __name__ == "__main__":
    main()
