# Copyright 2022- Python Language Server Contributors.

import logging
from typing import Any, Dict, Generator, List, Optional, Set

import parso
from jedi import Script
from parso.python import tree
from parso.tree import NodeOrLeaf
from rope.base.resources import Resource
from rope.contrib.autoimport.defs import SearchResult
from rope.contrib.autoimport.sqlite import AutoImport

from pylsp import hookimpl
from pylsp.config.config import Config
from pylsp.workspace import Document, Workspace

from ._rope_task_handle import PylspTaskHandle

log = logging.getLogger(__name__)

_score_pow = 5
_score_max = 10**_score_pow
MAX_RESULTS = 1000


@hookimpl
def pylsp_settings() -> Dict[str, Dict[str, Dict[str, Any]]]:
    # Default rope_completion to disabled
    return {"plugins": {"rope_autoimport": {"enabled": False, "memory": False}}}


def _should_insert(expr: tree.BaseNode, word_node: tree.Leaf) -> bool:  # pylint: disable=too-many-return-statements
    """
    Check if we should insert the word_node on the given expr.

    Works for both correct and incorrect code. This is because the
    user is often working on the code as they write it.
    """
    if not word_node:
        return False
    if len(expr.children) == 0:
        return True
    first_child = expr.children[0]
    if isinstance(first_child, tree.EndMarker):
        if "#" in first_child.prefix:
            return False  # Check for single line comment
    if first_child == word_node:
        return True  # If the word is the first word then its fine
    if len(expr.children) > 1:
        if any(
            node.type == "operator" and "." in node.value or node.type == "trailer"
            for node in expr.children
        ):
            return False  # Check if we're on a method of a function
    if isinstance(first_child, (tree.PythonErrorNode, tree.PythonNode)):
        # The tree will often include error nodes like this to indicate errors
        # we want to ignore errors since the code is being written
        return _should_insert(first_child, word_node)
    return _handle_first_child(first_child, expr, word_node)


def _handle_first_child(first_child: NodeOrLeaf, expr: tree.BaseNode, word_node: tree.Leaf) -> bool:
    """Check if we suggest imports given the following first child."""
    if isinstance(first_child, tree.Import):
        return False
    if isinstance(first_child, (tree.PythonLeaf, tree.PythonErrorLeaf)):
        # Check if the first item is a from or import statement even when incomplete
        if first_child.value in ("import", "from"):
            return False
    if isinstance(first_child, tree.Keyword):
        if first_child.value == "def":
            return _should_import_function(word_node, expr)
        if first_child.value == "class":
            return _should_import_class(word_node, expr)
    return True


def _should_import_class(word_node: tree.Leaf, expr: tree.BaseNode) -> bool:
    prev_node = None
    for node in expr.children:
        if isinstance(node, tree.Name):
            if isinstance(prev_node, tree.Operator):
                if node == word_node and prev_node.value == "(":
                    return True
        prev_node = node

    return False


def _should_import_function(word_node: tree.Leaf, expr: tree.BaseNode) -> bool:
    prev_node = None
    for node in expr.children:
        if _handle_argument(node, word_node):
            return True
        if isinstance(prev_node, tree.Operator):
            if prev_node.value == "->":
                if node == word_node:
                    return True
        prev_node = node
    return False


def _handle_argument(node: NodeOrLeaf, word_node: tree.Leaf):
    if isinstance(node, tree.PythonNode):
        if node.type == "tfpdef":
            if node.children[2] == word_node:
                return True
        if node.type == "parameters":
            for parameter in node.children:
                if _handle_argument(parameter, word_node):
                    return True
    return False


def _process_statements(
    suggestions: List[SearchResult],
    doc_uri: str,
    word: str,
    autoimport: AutoImport,
    document: Document,
) -> Generator[Dict[str, Any], None, None]:
    for suggestion in suggestions:
        insert_line = autoimport.find_insertion_line(document.source) - 1
        start = {"line": insert_line, "character": 0}
        edit_range = {"start": start, "end": start}
        edit = {"range": edit_range, "newText": suggestion.import_statement + "\n"}
        score = _get_score(suggestion.source, suggestion.import_statement, suggestion.name, word)
        if score > _score_max:
            continue
        # TODO make this markdown
        yield {
            "label": suggestion.name,
            "kind": suggestion.itemkind,
            "sortText": _sort_import(score),
            "data": {"doc_uri": doc_uri},
            "detail": _document(suggestion.import_statement),
            "additionalTextEdits": [edit],
        }


def get_names(script: Script) -> Set[str]:
    """Get all names to ignore from the current file."""
    raw_names = script.get_names(definitions=True)
    log.debug(raw_names)
    return set(name.name for name in raw_names)


@hookimpl
def pylsp_completions(config: Config, workspace: Workspace, document: Document, position):
    """Get autoimport suggestions."""
    line = document.lines[position["line"]]
    expr = parso.parse(line)
    word_node = expr.get_leaf_for_position((1, position["character"]))
    if not _should_insert(expr, word_node):
        return []
    word = word_node.value
    log.debug(f"autoimport: searching for word: {word}")
    rope_config = config.settings(document_path=document.path).get("rope", {})
    ignored_names: Set[str] = get_names(document.jedi_script(use_document_path=True))
    autoimport = workspace._rope_autoimport(rope_config)
    suggestions = list(autoimport.search_full(word, ignored_names=ignored_names))
    results = list(
        sorted(
            _process_statements(suggestions, document.uri, word, autoimport, document),
            key=lambda statement: statement["sortText"],
        )
    )
    if len(results) > MAX_RESULTS:
        results = results[:MAX_RESULTS]
    return results


def _document(import_statement: str) -> str:
    return """# Auto-Import\n""" + import_statement


def _get_score(source: int, full_statement: str, suggested_name: str, desired_name) -> int:
    import_length = len("import")
    full_statement_score = len(full_statement) - import_length
    suggested_name_score = ((len(suggested_name) - len(desired_name))) ** 2
    source_score = 20 * source
    return suggested_name_score + full_statement_score + source_score


def _sort_import(score: int) -> str:
    score = max(min(score, (_score_max) - 1), 0)
    # Since we are using ints, we need to pad them.
    # We also want to prioritize autoimport behind everything since its the last priority.
    # The minimum is to prevent score from overflowing the pad
    return "[z" + str(score).rjust(_score_pow, "0")


def _reload_cache(config: Config, workspace: Workspace, files: Optional[List[Document]] = None):
    memory: bool = config.plugin_settings("rope_autoimport").get("memory", False)
    rope_config = config.settings().get("rope", {})
    autoimport = workspace._rope_autoimport(rope_config, memory)
    task_handle = PylspTaskHandle(workspace)
    resources: Optional[List[Resource]] = (
        None if files is None else [document._rope_resource(rope_config) for document in files]
    )
    autoimport.generate_cache(task_handle=task_handle, resources=resources)
    autoimport.generate_modules_cache(task_handle=task_handle)


@hookimpl
def pylsp_initialize(config: Config, workspace: Workspace):
    """Initialize AutoImport.

    Generates the cache for local and global items.
    """
    _reload_cache(config, workspace)


@hookimpl
def pylsp_document_did_open(config: Config, workspace: Workspace):
    """Initialize AutoImport.

    Generates the cache for local and global items.
    """
    _reload_cache(config, workspace)


@hookimpl
def pylsp_document_did_save(config: Config, workspace: Workspace, document: Document):
    """Update the names associated with this document."""
    _reload_cache(config, workspace, [document])
