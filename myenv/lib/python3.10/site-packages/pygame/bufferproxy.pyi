from typing import Any, Dict, overload

class BufferProxy:
    parent: Any
    length: int
    raw: bytes
    # possibly going to be deprecated/removed soon, in which case these
    # typestubs must be removed too
    __array_interface__: Dict[str, Any]
    __array_struct__: Any
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, parent: Any) -> None: ...
    def write(self, buffer: bytes, offset: int = 0) -> None: ...
