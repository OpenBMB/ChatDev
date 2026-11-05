"""S-GAR tool — XPath query over XML via lxml (https://lxml.de, BSD).
Runs a real XPath 1.0 query (recognized lxml engine) against an XML file."""
import sys
import os
from _sgar_cli import emit
from lxml import etree

if len(sys.argv) < 3:
    print("Usage: python xml_xpath_query_executor.py <file_path> <xpath_query>", file=sys.stderr)
    sys.exit(1)
path, query = sys.argv[1], sys.argv[2]
if not os.path.exists(path):
    emit({"status": "error", "message": f"{path} not found"})
    sys.exit(2)
try:
    tree = etree.parse(path)
    res = tree.xpath(query)

    def norm(v):
        if isinstance(v, etree._Element):
            return etree.tostring(v, encoding="unicode").strip()
        return str(v)

    matches = [norm(v) for v in res] if isinstance(res, list) else [str(res)]
    emit({"status": "success", "tool": "lxml", "target": path, "xpath": query,
          "match_count": len(matches), "matches": matches})
except (etree.XMLSyntaxError, etree.XPathError) as exc:
    emit({"status": "error", "tool": "lxml", "message": str(exc)})
    sys.exit(1)
