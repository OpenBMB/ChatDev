# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

import logging

from rope.base import libutils
from rope.refactor.rename import Rename

from pylsp import hookimpl, uris

log = logging.getLogger(__name__)


@hookimpl
def pylsp_settings():
    # Default rope_rename to disabled
    return {'plugins': {'rope_rename': {'enabled': False}}}


@hookimpl
def pylsp_rename(config, workspace, document, position, new_name):
    with workspace.report_progress("rename"):
        rope_config = config.settings(document_path=document.path).get('rope', {})
        rope_project = workspace._rope_project_builder(rope_config)

        rename = Rename(
            rope_project,
            libutils.path_to_resource(rope_project, document.path),
            document.offset_at_position(position)
        )

        log.debug("Executing rename of %s to %s", document.word_at_position(position), new_name)
        changeset = rename.get_changes(new_name, in_hierarchy=True, docs=True)
        log.debug("Finished rename: %s", changeset.changes)
        changes = []
        for change in changeset.changes:
            uri = uris.from_fs_path(change.resource.path)
            doc = workspace.get_maybe_document(uri)
            changes.append({
                'textDocument': {
                    'uri': uri,
                    'version': doc.version if doc else None
                },
                'edits': [
                    {
                        'range': {
                            'start': {'line': 0, 'character': 0},
                            'end': {
                                'line': _num_lines(change.resource),
                                'character': 0,
                            },
                        },
                        'newText': change.new_contents,
                    }
                ]
            })
        return {'documentChanges': changes}


def _num_lines(resource):
    "Count the number of lines in a `File` resource."
    return len(resource.read().splitlines())
