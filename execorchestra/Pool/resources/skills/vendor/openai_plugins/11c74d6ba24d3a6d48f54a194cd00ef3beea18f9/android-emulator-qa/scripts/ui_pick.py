#!/usr/bin/env python3
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def read_trimmed_xml(path: Path) -> str:
    text = path.read_text()
    end = text.find("</hierarchy>")
    if end == -1:
        raise ValueError("end tag not found")
    return text[: end + len("</hierarchy>")]


def find_node(root: ET.Element, target: str) -> ET.Element | None:
    normalized_target = clean_text(target)
    for element in root.iter():
        text = clean_text(element.attrib.get("text"))
        desc = clean_text(element.attrib.get("content-desc"))
        if text == normalized_target or desc == normalized_target:
            return element
    return None


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: ui_pick.py <ui_dump.xml> <target_text>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    target = sys.argv[2]

    try:
        trimmed_xml = read_trimmed_xml(path)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        root = ET.fromstring(trimmed_xml)
    except ET.ParseError as exc:
        print(f"error: failed to parse xml: {exc}", file=sys.stderr)
        return 2

    node = find_node(root, target)
    if node is None:
        print("error: node not found", file=sys.stderr)
        return 2

    bounds = node.attrib.get("bounds", "")
    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
    if not match:
        print("error: bounds not found", file=sys.stderr)
        return 2

    x1, y1, x2, y2 = map(int, match.groups())
    x = (x1 + x2) // 2
    y = (y1 + y2) // 2
    print(f"{x} {y}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
