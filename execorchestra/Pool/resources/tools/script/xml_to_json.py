"""S-GAR tool — XML→JSON conversion via lxml (https://lxml.de, BSD).
Parses XML with the recognized lxml library and emits a JSON tree
(tag / attributes / text / children)."""
import sys
import os
from _sgar_cli import emit
from lxml import etree


def elem_to_dict(el):
    node = {"tag": etree.QName(el).localname, "attrib": dict(el.attrib)}
    text = (el.text or "").strip()
    if text:
        node["text"] = text
    children = [elem_to_dict(c) for c in el if isinstance(c.tag, str)]
    if children:
        node["children"] = children
    return node


if len(sys.argv) < 2:
    print("Usage: python xml_to_json.py <file_path>", file=sys.stderr)
    sys.exit(1)
path = sys.argv[1]
if not os.path.exists(path):
    emit({"status": "error", "message": f"{path} not found"})
    sys.exit(2)
try:
    tree = etree.parse(path)
    emit({"status": "success", "tool": "lxml", "target": path, "json": elem_to_dict(tree.getroot())})
except etree.XMLSyntaxError as exc:
    emit({"status": "error", "tool": "lxml", "message": f"invalid XML: {exc}"})
    sys.exit(1)
