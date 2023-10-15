# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

import logging
import re
from pylsp import hookimpl, _utils

log = logging.getLogger(__name__)

SPHINX = re.compile(r"\s*:param\s+(?P<param>\w+):\s*(?P<doc>[^\n]+)")
EPYDOC = re.compile(r"\s*@param\s+(?P<param>\w+):\s*(?P<doc>[^\n]+)")
GOOGLE = re.compile(r"\s*(?P<param>\w+).*:\s*(?P<doc>[^\n]+)")

DOC_REGEX = [SPHINX, EPYDOC, GOOGLE]


@hookimpl
def pylsp_signature_help(config, document, position):
    code_position = _utils.position_to_jedi_linecolumn(document, position)
    signatures = document.jedi_script().get_signatures(**code_position)

    if not signatures:
        return {'signatures': []}

    signature_capabilities = config.capabilities.get('textDocument', {}).get('signatureHelp', {})
    signature_information_support = signature_capabilities.get('signatureInformation', {})
    supported_markup_kinds = signature_information_support.get('documentationFormat', ['markdown'])
    preferred_markup_kind = _utils.choose_markup_kind(supported_markup_kinds)

    s = signatures[0]

    docstring = s.docstring()

    # Docstring contains one or more lines of signature, followed by empty line, followed by docstring
    function_sig_lines = (docstring.split('\n\n') or [''])[0].splitlines()
    function_sig = ' '.join([line.strip() for line in function_sig_lines])
    sig = {
        'label': function_sig,
        'documentation': _utils.format_docstring(
            s.docstring(raw=True),
            markup_kind=preferred_markup_kind
        )
    }

    # If there are params, add those
    if s.params:
        sig['parameters'] = [{
            'label': p.name,
            'documentation': _utils.format_docstring(
                _param_docs(docstring, p.name),
                markup_kind=preferred_markup_kind
            )
        } for p in s.params]

    # We only return a single signature because Python doesn't allow overloading
    sig_info = {'signatures': [sig], 'activeSignature': 0}

    if s.index is not None and s.params:
        # Then we know which parameter we're looking at
        sig_info['activeParameter'] = s.index

    return sig_info


def _param_docs(docstring, param_name):
    for line in docstring.splitlines():
        for regex in DOC_REGEX:
            m = regex.match(line)
            if not m:
                continue
            if m.group('param') != param_name:
                continue
            return m.group('doc') or ""
