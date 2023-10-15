from typing import Callable, List

AUDIO_U8: int
AUDIO_S8: int
AUDIO_U16LSB: int
AUDIO_S16LSB: int
AUDIO_U16MSB: int
AUDIO_S16MSB: int
AUDIO_U16: int
AUDIO_S16: int
AUDIO_S32LSB: int
AUDIO_S32MSB: int
AUDIO_S32: int
AUDIO_F32LSB: int
AUDIO_F32MSB: int
AUDIO_F32: int

AUDIO_ALLOW_FREQUENCY_CHANGE: int
AUDIO_ALLOW_FORMAT_CHANGE: int
AUDIO_ALLOW_CHANNELS_CHANGE: int
AUDIO_ALLOW_ANY_CHANGE: int

def get_audio_device_names(iscapture: bool = False) -> List[str]: ...

class AudioDevice:
    def __init__(
        self,
        devicename: str,
        iscapture: bool,
        frequency: int,
        audioformat: int,
        numchannels: int,
        chunksize: int,
        allowed_changes: int,
        callback: Callable[[AudioDevice, memoryview], None],
    ) -> None: ...
    @property
    def iscapture(self) -> bool: ...
    @property
    def deviceid(self) -> int: ...
    @property
    def devicename(self) -> str: ...
    @property
    def callback(self) -> Callable[[AudioDevice, memoryview], None]: ...
    @property
    def frequency(self) -> int: ...
    @property
    def audioformat(self) -> int: ...
    @property
    def numchannels(self) -> int: ...
    @property
    def chunksize(self) -> int: ...
    def pause(self, pause_on: int) -> None: ...
    def close(self) -> None: ...
