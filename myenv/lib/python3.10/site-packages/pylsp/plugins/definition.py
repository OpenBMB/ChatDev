# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

import logging
from pylsp import hookimpl, uris, _utils

log = logging.getLogger(__name__)


@hookimpl
def pylsp_definitions(config, workspace, document, position):
    with workspace.report_progress("go to definitions"):
        settings = config.plugin_settings('jedi_definition')
        code_position = _utils.position_to_jedi_linecolumn(document, position)
        definitions = document.jedi_script(use_document_path=True).goto(
            follow_imports=settings.get('follow_imports', True),
            follow_builtin_imports=settings.get('follow_builtin_imports', True),
            **code_position)

        follow_builtin_defns = settings.get("follow_builtin_definitions", True)
        return [
            {
                'uri': uris.uri_with(document.uri, path=str(d.module_path)),
                'range': {
                    'start': {'line': d.line - 1, 'character': d.column},
                    'end': {'line': d.line - 1, 'character': d.column + len(d.name)},
                }
            }
            for d in definitions if d.is_definition() and (follow_builtin_defns or _not_internal_definition(d))
        ]


def _not_internal_definition(definition):
    return (
        definition.line is not None and
        definition.column is not None and
        definition.module_path is not None and
        not definition.in_builtin_module()
    )
