"""pygame.camera backend that uses OpenCV.

Uses the cv2 module opencv for python.
See https://pypi.org/project/opencv-python/ for wheels version.

python3 -m pip install opencv-python --user
"""
import numpy
import cv2
import time

import pygame


def list_cameras():
    """ """
    index = 0
    device_idx = []
    failed = 0

    # Sometimes there are gaps between the device index.
    # We keep trying max_gaps times.
    max_gaps = 3

    while failed < max_gaps:
        vcap = cv2.VideoCapture(index)
        if not vcap.read()[0]:
            failed += 1
        else:
            device_idx.append(index)
        vcap.release()
        index += 1
    return device_idx


def list_cameras_darwin():
    import subprocess
    from xml.etree import ElementTree

    # pylint: disable=consider-using-with
    flout, _ = subprocess.Popen(
        "system_profiler -xml SPCameraDataType",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).communicate()

    last_text = None
    cameras = []

    for node in ElementTree.fromstring(flout).iterfind("./array/dict/array/dict/*"):
        if last_text == "_name":
            cameras.append(node.text)
        last_text = node.text

    return cameras


class Camera:
    def __init__(self, device=0, size=(640, 480), mode="RGB", api_preference=None):
        """
        api_preference - cv2.CAP_DSHOW cv2.CAP_V4L2 cv2.CAP_MSMF and others

        # See https://docs.opencv.org/3.4/d4/d15/group__videoio__flags__base.html
        """
        self._device_index = device
        self._size = size

        self.api_preference = api_preference
        if api_preference is not None:
            if sys.platform == "win32":
                # seems more compatible on windows?
                self.api_preference = cv2.CAP_DSHOW

        if mode == "RGB":
            self._fmt = cv2.COLOR_BGR2RGB
        elif mode == "YUV":
            self._fmt = cv2.COLOR_BGR2YUV
        elif mode == "HSV":
            self._fmt = cv2.COLOR_BGR2HSV
        else:
            raise ValueError("Not a supported mode")

        self._open = False

    # all of this could have been done in the constructor, but creating
    # the VideoCapture is very time consuming, so it makes more sense in the
    # actual start() method
    def start(self):
        if self._open:
            return

        self._cam = cv2.VideoCapture(self._device_index, self.api_preference)

        if not self._cam.isOpened():
            raise ValueError("Could not open camera.")

        self._cam.set(cv2.CAP_PROP_FRAME_WIDTH, self._size[0])
        self._cam.set(cv2.CAP_PROP_FRAME_HEIGHT, self._size[1])

        w = self._cam.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = self._cam.get(cv2.CAP_PROP_FRAME_HEIGHT)
        self._size = (int(w), int(h))

        self._flipx = False
        self._flipy = False
        self._brightness = 1

        self._frametime = 1 / self._cam.get(cv2.CAP_PROP_FPS)
        self._last_frame_time = 0

        self._open = True

    def stop(self):
        if self._open:
            self._cam.release()
            self._cam = None
            self._open = False

    def _check_open(self):
        if not self._open:
            raise pygame.error("Camera must be started")

    def get_size(self):
        self._check_open()

        return self._size

    def set_controls(self, hflip=None, vflip=None, brightness=None):
        self._check_open()

        if hflip is not None:
            self._flipx = bool(hflip)
        if vflip is not None:
            self._flipy = bool(vflip)
        if brightness is not None:
            self._cam.set(cv2.CAP_PROP_BRIGHTNESS, brightness)

        return self.get_controls()

    def get_controls(self):
        self._check_open()

        return (self._flipx, self._flipy, self._cam.get(cv2.CAP_PROP_BRIGHTNESS))

    def query_image(self):
        self._check_open()

        current_time = time.time()
        if current_time - self._last_frame_time > self._frametime:
            return True
        return False

    def get_image(self, dest_surf=None):
        self._check_open()

        self._last_frame_time = time.time()

        _, image = self._cam.read()

        image = cv2.cvtColor(image, self._fmt)

        flip_code = None
        if self._flipx:
            if self._flipy:
                flip_code = -1
            else:
                flip_code = 1
        elif self._flipy:
            flip_code = 0

        if flip_code is not None:
            image = cv2.flip(image, flip_code)

        image = numpy.fliplr(image)
        image = numpy.rot90(image)

        surf = pygame.surfarray.make_surface(image)

        if dest_surf:
            dest_surf.blit(surf, (0, 0))
            return dest_surf

        return surf

    def get_raw(self):
        self._check_open()

        self._last_frame_time = time.time()

        _, image = self._cam.read()

        return image.tobytes()


class CameraMac(Camera):
    def __init__(self, device=0, size=(640, 480), mode="RGB", api_preference=None):
        if isinstance(device, int):
            _dev = device
        elif isinstance(device, str):
            _dev = list_cameras_darwin().index(device)
        else:
            raise TypeError(
                "OpenCV-Mac backend can take device indices or names, ints or strings, not ",
                str(type(device)),
            )

        super().__init__(_dev, size, mode, api_preference)
