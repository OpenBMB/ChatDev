# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

import logging

from pylsp import hookimpl, uris, _utils

log = logging.getLogger(__name__)


@hookimpl
def pylsp_rename(config, workspace, document, position, new_name):  # pylint: disable=unused-argument,too-many-locals
    with workspace.report_progress("rename", percentage=0) as report_progress:
        log.debug('Executing rename of %s to %s', document.word_at_position(position), new_name)
        kwargs = _utils.position_to_jedi_linecolumn(document, position)
        kwargs['new_name'] = new_name
        report_progress("refactoring")
        try:
            refactoring = document.jedi_script().rename(**kwargs)
        except NotImplementedError as exc:
            raise Exception('No support for renaming in Python 2/3.5 with Jedi. '
                            'Consider using the rope_rename plugin instead') from exc
        log.debug('Finished rename: %s', refactoring.get_diff())
        changes = []

        changed_files = refactoring.get_changed_files()
        for n, (file_path, changed_file) in enumerate(changed_files.items()):
            report_progress(changed_file, percentage=n/len(changed_files)*100)
            uri = uris.from_fs_path(str(file_path))
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
                                'line': _num_lines(changed_file.get_new_code()),
                                'character': 0,
                            },
                        },
                        'newText': changed_file.get_new_code(),
                    }
                ],
            })
        return {'documentChanges': changes}


def _num_lines(file_contents):
    'Count the number of lines in the given string.'
    return len(file_contents.splitlines())
