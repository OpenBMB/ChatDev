# python -m pygame.docs

import os
import webbrowser
from urllib.parse import quote, urlunparse


def _iterpath(path):
    path, last = os.path.split(path)
    if last:
        yield from _iterpath(path)
        yield last


# for test suite to confirm pygame built with local docs
def has_local_docs():
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    main_page = os.path.join(pkg_dir, "generated", "index.html")
    return os.path.exists(main_page)


def open_docs():
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    main_page = os.path.join(pkg_dir, "generated", "index.html")
    if os.path.exists(main_page):
        url_path = quote("/".join(_iterpath(main_page)))
        drive, rest = os.path.splitdrive(__file__)
        if drive:
            url_path = f"{drive}/{url_path}"
        url = urlunparse(("file", "", url_path, "", "", ""))
    else:
        url = "https://www.pygame.org/docs/"
    webbrowser.open(url)


if __name__ == "__main__":
    open_docs()
