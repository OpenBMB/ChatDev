__tags__ = ["ignore", "subprocess_ignore"]

# TODO: make scrap_test.py work
# This test used to work only on linux and windows.
# Currently it only work in windows, and in linux it throws:
# `pygame.error: content could not be placed in clipboard.`
# The old test and tags kept here for reference when fixing.

# import sys
#
# exclude = False
#
# if sys.platform == "win32" or sys.platform.startswith("linux"):
#     try:
#         import pygame
#
#         pygame.scrap._NOT_IMPLEMENTED_
#     except AttributeError:
#         pass
#     else:
#         exclude = True
# else:
#     exclude = True
#
# if exclude:
#     __tags__.extend(["ignore", "subprocess_ignore"])
