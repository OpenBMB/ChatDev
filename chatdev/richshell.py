import difflib
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
import textwrap

def color_code_diff(code1: str, code2: str, node1: int, node2: int):

    code1 = code1.strip()
    code2 = code2.strip()

    diff = difflib.ndiff(code1.splitlines(), code2.splitlines())
    
    console = Console()

    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Line #", justify="right", style="cyan", no_wrap=True)  
    table.add_column("Node {}'s Solution".format(node1), justify="left", style="green", overflow="fold")  
    table.add_column("Node {}'s Solution".format(node2), justify="left", style="red", overflow="fold")  

    line_num = 0
    line_num1, line_num2 = 0, 0

    for line in diff:
        if line.startswith('-'):
            line_num1 += 1
            line_num += 1
            table.add_row(f"{line_num}", Text(line[2:], style="bold red"), "")
        elif line.startswith('+'):
            line_num2 += 1
            line_num += 1
            table.add_row(f"{line_num}", "", Text(line[2:], style="bold green"))
        elif line.startswith(' '):
            line_num1 += 1
            line_num2 += 1
            line_num += 1
            table.add_row(f"{line_num}", Text(line[2:], style="white"), Text(line[2:], style="white"))

    panel = Panel(table, title="Code Diff", border_style="bold blue")
    console.print(panel)

def justify_in_box(text: str, width: int = 200, title: str = "Text Box"):
    console = Console()

    justified_text = "\n".join(
        [textwrap.fill(line, width=width, expand_tabs=False) for line in text.splitlines()]
    )

    rich_text = Text(justified_text, justify="full")

    panel = Panel(rich_text, title=title, expand=False)

    console.print(panel)
