"""pygame.camera.Camera implementation using the videocapture module for windows.

http://videocapture.sourceforge.net/

Binary windows wheels:
  https://www.lfd.uci.edu/~gohlke/pythonlibs/#videocapture
"""
import pygame


def list_cameras():
    """Always only lists one camera.

    Functionality not supported in videocapture module.
    """
    return [0]

    # this just cycles through all the cameras trying to open them
    # cameras = []
    # for x in range(256):
    #    try:
    #        c = Camera(x)
    #    except:
    #        break
    #    cameras.append(x)
    # return cameras


def init():
    global vidcap
    try:
        import vidcap as vc
    except ImportError:
        from VideoCapture import vidcap as vc
    vidcap = vc


def quit():
    global vidcap
    vidcap = None


class Camera:
    # pylint: disable=unused-argument
    def __init__(self, device=0, size=(640, 480), mode="RGB", show_video_window=0):
        """device:  VideoCapture enumerates the available video capture devices
                 on your system.  If you have more than one device, specify
                 the desired one here.  The device number starts from 0.

        show_video_window: 0 ... do not display a video window (the default)
                           1 ... display a video window

                         Mainly used for debugging, since the video window
                         can not be closed or moved around.
        """
        self.dev = vidcap.new_Dev(device, show_video_window)
        width, height = size
        self.dev.setresolution(width, height)

    def display_capture_filter_properties(self):
        """Displays a dialog containing the property page of the capture filter.

        For VfW drivers you may find the option to select the resolution most
        likely here.
        """
        self.dev.displaycapturefilterproperties()

    def display_capture_pin_properties(self):
        """Displays a dialog containing the property page of the capture pin.

        For WDM drivers you may find the option to select the resolution most
        likely here.
        """
        self.dev.displaycapturepinproperties()

    def set_resolution(self, width, height):
        """Sets the capture resolution. (without dialog)"""
        self.dev.setresolution(width, height)

    def get_buffer(self):
        """Returns a string containing the raw pixel data."""
        return self.dev.getbuffer()

    def start(self):
        """Not implemented."""

    def set_controls(self, **kwargs):
        """Not implemented."""

    def stop(self):
        """Not implemented."""

    def get_image(self, dest_surf=None):
        """ """
        return self.get_surface(dest_surf)

    def get_surface(self, dest_surf=None):
        """Returns a pygame Surface."""
        abuffer, width, height = self.get_buffer()
        if not abuffer:
            return None
        surf = pygame.image.frombuffer(abuffer, (width, height), "BGR")
        surf = pygame.transform.flip(surf, 0, 1)
        # if there is a destination surface given, we blit onto that.
        if dest_surf:
            dest_surf.blit(surf, (0, 0))
        else:
            dest_surf = surf
        return dest_surf


if __name__ == "__main__":
    import pygame.examples.camera

    pygame.camera.Camera = Camera
    pygame.camera.list_cameras = list_cameras
    pygame.examples.camera.main()
