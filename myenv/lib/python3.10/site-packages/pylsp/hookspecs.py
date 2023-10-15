# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

# pylint: disable=redefined-builtin, unused-argument
from pylsp import hookspec


@hookspec
def pylsp_code_actions(config, workspace, document, range, context):
    pass


@hookspec
def pylsp_code_lens(config, workspace, document):
    pass


@hookspec
def pylsp_commands(config, workspace):
    """The list of command strings supported by the server.

    Returns:
        List[str]: The supported commands.
    """


@hookspec
def pylsp_completions(config, workspace, document, position):
    pass


@hookspec(firstresult=True)
def pylsp_completion_item_resolve(config, workspace, document, completion_item):
    pass


@hookspec
def pylsp_definitions(config, workspace, document, position):
    pass


@hookspec
def pylsp_dispatchers(config, workspace):
    pass


@hookspec
def pylsp_document_did_open(config, workspace, document):
    pass


@hookspec
def pylsp_document_did_save(config, workspace, document):
    pass


@hookspec
def pylsp_document_highlight(config, workspace, document, position):
    pass


@hookspec
def pylsp_document_symbols(config, workspace, document):
    pass


@hookspec(firstresult=True)
def pylsp_execute_command(config, workspace, command, arguments):
    pass


@hookspec
def pylsp_experimental_capabilities(config, workspace):
    pass


@hookspec
def pylsp_folding_range(config, workspace, document):
    pass


@hookspec(firstresult=True)
def pylsp_format_document(config, workspace, document, options):
    pass


@hookspec(firstresult=True)
def pylsp_format_range(config, workspace, document, range, options):
    pass


@hookspec(firstresult=True)
def pylsp_hover(config, workspace, document, position):
    pass


@hookspec
def pylsp_initialize(config, workspace):
    pass


@hookspec
def pylsp_initialized():
    pass


@hookspec
def pylsp_lint(config, workspace, document, is_saved):
    pass


@hookspec
def pylsp_references(config, workspace, document, position, exclude_declaration):
    pass


@hookspec(firstresult=True)
def pylsp_rename(config, workspace, document, position, new_name):
    pass


@hookspec
def pylsp_settings(config):
    pass


@hookspec(firstresult=True)
def pylsp_signature_help(config, workspace, document, position):
    pass
