# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.const import PY39_PLUS
from astroid.manager import AstroidManager


def _hashlib_transform():
    maybe_usedforsecurity = ", usedforsecurity=True" if PY39_PLUS else ""
    init_signature = f"value=''{maybe_usedforsecurity}"
    digest_signature = "self"
    shake_digest_signature = "self, length"

    template = """
    class %(name)s:
        def __init__(self, %(init_signature)s): pass
        def digest(%(digest_signature)s):
            return %(digest)s
        def copy(self):
            return self
        def update(self, value): pass
        def hexdigest(%(digest_signature)s):
            return ''
        @property
        def name(self):
            return %(name)r
        @property
        def block_size(self):
            return 1
        @property
        def digest_size(self):
            return 1
    """

    algorithms_with_signature = dict.fromkeys(
        [
            "md5",
            "sha1",
            "sha224",
            "sha256",
            "sha384",
            "sha512",
            "sha3_224",
            "sha3_256",
            "sha3_384",
            "sha3_512",
        ],
        (init_signature, digest_signature),
    )

    blake2b_signature = (
        "data=b'', *, digest_size=64, key=b'', salt=b'', "
        "person=b'', fanout=1, depth=1, leaf_size=0, node_offset=0, "
        f"node_depth=0, inner_size=0, last_node=False{maybe_usedforsecurity}"
    )

    blake2s_signature = (
        "data=b'', *, digest_size=32, key=b'', salt=b'', "
        "person=b'', fanout=1, depth=1, leaf_size=0, node_offset=0, "
        f"node_depth=0, inner_size=0, last_node=False{maybe_usedforsecurity}"
    )

    shake_algorithms = dict.fromkeys(
        ["shake_128", "shake_256"],
        (init_signature, shake_digest_signature),
    )
    algorithms_with_signature.update(shake_algorithms)

    algorithms_with_signature.update(
        {
            "blake2b": (blake2b_signature, digest_signature),
            "blake2s": (blake2s_signature, digest_signature),
        }
    )

    classes = "".join(
        template
        % {
            "name": hashfunc,
            "digest": 'b""',
            "init_signature": init_signature,
            "digest_signature": digest_signature,
        }
        for hashfunc, (
            init_signature,
            digest_signature,
        ) in algorithms_with_signature.items()
    )

    return parse(classes)


register_module_extender(AstroidManager(), "hashlib", _hashlib_transform)
