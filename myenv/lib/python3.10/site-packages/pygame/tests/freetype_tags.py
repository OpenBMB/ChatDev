__tags__ = ["development"]

exclude = False

try:
    import pygame.freetype
except ImportError:
    exclude = True

if exclude:
    __tags__.extend(["ignore", "subprocess_ignore"])
