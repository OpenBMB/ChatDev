#!/usr/bin/env python3
import re
import sys
import xml.etree.ElementTree as ET

INTERACTIVE_ATTRS = ("clickable", "long-clickable", "scrollable", "focusable")
STATE_ATTRS = ("checked", "selected")
DISPLAY_ATTRS = ("text", "content-desc", "resource-id")
MAX_DEPTH = 20


def clean_text(value):
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def is_true(value):
    return value == "true"


def simplify_class(value):
    if not value:
        return ""
    return value.split(".")[-1]


def simplify_resource_id(value):
    if not value:
        return ""
    if ":id/" in value:
        prefix, rest = value.split(":id/", 1)
        if prefix and prefix != "android":
            return "id/" + rest
    return value


def extract_labels(node):
    text = clean_text(node.attrib.get("text", ""))
    desc = clean_text(node.attrib.get("content-desc", ""))
    resource_id = simplify_resource_id(node.attrib.get("resource-id", ""))
    return text, desc, resource_id


def is_interactive(node):
    for key in INTERACTIVE_ATTRS:
        if is_true(node.attrib.get(key, "false")):
            return True
    return False


def has_display(node):
    text, desc, resource_id = extract_labels(node)
    return bool(text or desc or resource_id)


def keep_node(node):
    return has_display(node) or is_interactive(node) or is_true(node.attrib.get("scrollable", "false"))


def format_node(node):
    class_name = simplify_class(node.attrib.get("class", ""))
    text, desc, resource_id = extract_labels(node)
    parts = [class_name]
    if resource_id:
        parts.append(f"id={resource_id}")
    if text:
        parts.append(f'text="{text}"')
    if desc:
        parts.append(f'desc="{desc}"')
    flags = []
    for key in INTERACTIVE_ATTRS:
        if is_true(node.attrib.get(key, "false")):
            flags.append(key)
    for key in STATE_ATTRS:
        if is_true(node.attrib.get(key, "false")):
            flags.append(key)
    if flags:
        parts.append("flags=" + ",".join(flags))
    bounds = node.attrib.get("bounds", "")
    if bounds and (is_interactive(node) or has_display(node)):
        parts.append(f"bounds={bounds}")
    return " ".join(parts)


def build_lines(node, depth):
    if depth > MAX_DEPTH:
        return []
    include = keep_node(node)
    child_depth = depth + 1 if include else depth
    lines = []
    if include:
        lines.append(("  " * depth) + format_node(node))
    for child in node:
        lines.extend(build_lines(child, child_depth))
    return lines


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: ui_tree_summarize.py <input.xml> <output.txt>")
    input_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path, "r", encoding="utf-8") as handle:
        xml_text = handle.read()
    end_marker = "</hierarchy>"
    end_index = xml_text.rfind(end_marker)
    if end_index == -1:
        raise SystemExit("hierarchy end tag not found")
    xml_text = xml_text[: end_index + len(end_marker)]
    root = ET.fromstring(xml_text)

    lines = []
    for child in root:
        lines.extend(build_lines(child, 0))

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
        handle.write("\n")


if __name__ == "__main__":
    main()
