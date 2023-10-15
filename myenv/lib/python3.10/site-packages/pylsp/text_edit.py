# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

def get_well_formatted_range(lsp_range):
    start = lsp_range['start']
    end = lsp_range['end']

    if start['line'] > end['line'] or (start['line'] == end['line'] and start['character'] > end['character']):
        return {'start': end, 'end': start}

    return lsp_range


def get_well_formatted_edit(text_edit):
    lsp_range = get_well_formatted_range(text_edit['range'])
    if lsp_range != text_edit['range']:
        return {'newText': text_edit['newText'], 'range': lsp_range}

    return text_edit


def compare_text_edits(a, b):
    diff = a['range']['start']['line'] - b['range']['start']['line']
    if diff == 0:
        return a['range']['start']['character'] - b['range']['start']['character']

    return diff


def merge_sort_text_edits(text_edits):
    if len(text_edits) <= 1:
        return text_edits

    p = len(text_edits) // 2
    left = text_edits[:p]
    right = text_edits[p:]

    merge_sort_text_edits(left)
    merge_sort_text_edits(right)

    left_idx = 0
    right_idx = 0
    i = 0
    while left_idx < len(left) and right_idx < len(right):
        ret = compare_text_edits(left[left_idx], right[right_idx])
        if ret <= 0:
            #  smaller_equal -> take left to preserve order
            text_edits[i] = left[left_idx]
            i += 1
            left_idx += 1
        else:
            # greater -> take right
            text_edits[i] = right[right_idx]
            i += 1
            right_idx += 1
    while left_idx < len(left):
        text_edits[i] = left[left_idx]
        i += 1
        left_idx += 1
    while right_idx < len(right):
        text_edits[i] = right[right_idx]
        i += 1
        right_idx += 1
    return text_edits


class OverLappingTextEditException(Exception):
    """
    Text edits are expected to be sorted
    and compressed instead of overlapping.
    This error is raised when two edits
    are overlapping.
    """


def apply_text_edits(doc, text_edits):
    text = doc.source
    sorted_edits = merge_sort_text_edits(list(map(get_well_formatted_edit, text_edits)))
    last_modified_offset = 0
    spans = []
    for e in sorted_edits:
        start_offset = doc.offset_at_position(e['range']['start'])
        if start_offset < last_modified_offset:
            raise OverLappingTextEditException('overlapping edit')

        if start_offset > last_modified_offset:
            spans.append(text[last_modified_offset:start_offset])

        if len(e['newText']):
            spans.append(e['newText'])
        last_modified_offset = doc.offset_at_position(e['range']['end'])

    spans.append(text[last_modified_offset:])
    return ''.join(spans)
