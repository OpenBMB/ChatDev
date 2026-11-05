from _liblib import ok,err,a
from markdown_it import MarkdownIt
try: ok("lib.markdown_it_render",html=MarkdownIt().render(a(1)))
except Exception as e: err("lib.markdown_it_render",str(e))
