from _liblib import ok,err,a
from pygments import highlight; from pygments.lexers import get_lexer_by_name; from pygments.formatters import HtmlFormatter
try: ok("lib.pygments_highlight",html=highlight(a(1),get_lexer_by_name(a(2,"python")),HtmlFormatter())[:800])
except Exception as e: err("lib.pygments_highlight",str(e))
