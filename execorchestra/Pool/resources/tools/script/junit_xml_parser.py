"""S-GAR tool — JUnit XML report parser via lxml (https://lxml.de, BSD).
Parses a standard JUnit/xUnit results file and summarizes suites and cases."""
import sys
import os
from _sgar_cli import emit
from lxml import etree

if len(sys.argv) < 2:
    print("Usage: python junit_xml_parser.py <file_path>", file=sys.stderr)
    sys.exit(1)
path = sys.argv[1]
if not os.path.exists(path):
    emit({"status": "error", "message": f"{path} not found"})
    sys.exit(2)
try:
    root = etree.parse(path).getroot()
    suites = root.iter("testsuite") if root.tag != "testsuite" else [root]
    parsed = []
    for s in suites:
        cases = []
        for c in s.iter("testcase"):
            status = "passed"
            if c.find("failure") is not None:
                status = "failed"
            elif c.find("error") is not None:
                status = "error"
            elif c.find("skipped") is not None:
                status = "skipped"
            cases.append({"name": c.get("name"), "classname": c.get("classname"),
                          "time": c.get("time"), "status": status})
        parsed.append({
            "name": s.get("name"), "tests": s.get("tests"), "failures": s.get("failures"),
            "errors": s.get("errors"), "skipped": s.get("skipped"), "time": s.get("time"),
            "cases": cases,
        })
    emit({"status": "success", "tool": "lxml", "target": path, "suites": parsed})
except etree.XMLSyntaxError as exc:
    emit({"status": "error", "tool": "lxml", "message": f"invalid XML: {exc}"})
    sys.exit(1)
