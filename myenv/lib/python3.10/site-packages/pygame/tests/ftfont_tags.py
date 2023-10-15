__tags__ = ["development"]

exclude = False

try:
    import pygame.ftfont
except ImportError:
    exclude = True

if exclude:
    __tags__.extend(["ignore", "subprocess_ignore"])
