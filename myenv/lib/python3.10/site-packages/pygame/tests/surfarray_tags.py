__tags__ = ["array"]

exclude = False

try:
    import numpy
except ImportError:
    exclude = True
else:
    try:
        import pygame.pixelcopy
    except ImportError:
        exclude = True

if exclude:
    __tags__.extend(("ignore", "subprocess_ignore"))
