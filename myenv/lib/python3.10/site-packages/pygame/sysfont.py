# pygame - Python Game Library
# Copyright (C) 2000-2003  Pete Shinners
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this library; if not, write to the Free
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Pete Shinners
# pete@shinners.org
"""sysfont, used in the font module to find system fonts"""

import os
import sys
import warnings
from os.path import basename, dirname, exists, join, splitext

from pygame.font import Font

if sys.platform != "emscripten":
    if os.name == "nt":
        import winreg as _winreg
    import subprocess


OpenType_extensions = frozenset((".ttf", ".ttc", ".otf"))
Sysfonts = {}
Sysalias = {}

is_init = False


def _simplename(name):
    """create simple version of the font name"""
    # return alphanumeric characters of a string (converted to lowercase)
    return "".join(c.lower() for c in name if c.isalnum())


def _addfont(name, bold, italic, font, fontdict):
    """insert a font and style into the font dictionary"""
    if name not in fontdict:
        fontdict[name] = {}
    fontdict[name][bold, italic] = font


def initsysfonts_win32():
    """initialize fonts dictionary on Windows"""

    fontdir = join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    fonts = {}

    # add fonts entered in the registry
    microsoft_font_dirs = [
        "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Fonts",
        "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Fonts",
    ]

    for domain in [_winreg.HKEY_LOCAL_MACHINE, _winreg.HKEY_CURRENT_USER]:
        for font_dir in microsoft_font_dirs:
            try:
                key = _winreg.OpenKey(domain, font_dir)
            except FileNotFoundError:
                continue

            for i in range(_winreg.QueryInfoKey(key)[1]):
                try:
                    # name is the font's name e.g. Times New Roman (TrueType)
                    # font is the font's filename e.g. times.ttf
                    name, font, _ = _winreg.EnumValue(key, i)
                except OSError:
                    break

                if splitext(font)[1].lower() not in OpenType_extensions:
                    continue
                if not dirname(font):
                    font = join(fontdir, font)

                # Some are named A & B, both names should be processed separately
                # Ex: the main Cambria file is marked as "Cambria & Cambria Math"
                for name in name.split("&"):
                    _parse_font_entry_win(name, font, fonts)

    return fonts


def _parse_font_entry_win(name, font, fonts):
    """
    Parse out a simpler name and the font style from the initial file name.

    :param name: The font name
    :param font: The font file path
    :param fonts: The pygame font dictionary
    """
    true_type_suffix = "(TrueType)"
    mods = ("demibold", "narrow", "light", "unicode", "bt", "mt")
    if name.endswith(true_type_suffix):
        name = name.rstrip(true_type_suffix).rstrip()
    name = name.lower().split()
    bold = italic = False
    for mod in mods:
        if mod in name:
            name.remove(mod)
    if "bold" in name:
        name.remove("bold")
        bold = True
    if "italic" in name:
        name.remove("italic")
        italic = True
    name = "".join(name)
    name = _simplename(name)

    _addfont(name, bold, italic, font, fonts)


def _parse_font_entry_darwin(name, filepath, fonts):
    """
    Parses a font entry for macOS

    :param name: The filepath without extensions or directories
    :param filepath: The full path to the font
    :param fonts: The pygame font dictionary to add the parsed font data to.
    """

    name = _simplename(name)

    mods = ("regular",)

    for mod in mods:
        if mod in name:
            name = name.replace(mod, "")

    bold = italic = False
    if "bold" in name:
        name = name.replace("bold", "")
        bold = True
    if "italic" in name:
        name = name.replace("italic", "")
        italic = True

    _addfont(name, bold, italic, filepath, fonts)


def _font_finder_darwin():
    locations = [
        "/Library/Fonts",
        "/Network/Library/Fonts",
        "/System/Library/Fonts",
        "/System/Library/Fonts/Supplemental",
    ]

    username = os.getenv("USER")
    if username:
        locations.append(f"/Users/{username}/Library/Fonts")

    strange_root = "/System/Library/Assets/com_apple_MobileAsset_Font3"
    if exists(strange_root):
        strange_locations = os.listdir(strange_root)
        for loc in strange_locations:
            locations.append(f"{strange_root}/{loc}/AssetData")

    fonts = {}

    for location in locations:
        if not exists(location):
            continue

        files = os.listdir(location)
        for file in files:
            name, extension = splitext(file)
            if extension in OpenType_extensions:
                _parse_font_entry_darwin(name, join(location, file), fonts)

    return fonts


def initsysfonts_darwin():
    """Read the fonts on MacOS, and OS X."""
    #  fc-list is not likely to be there on pre 10.4.x, or MacOS 10.10+
    fonts = {}

    fclist_locations = [
        "/usr/X11/bin/fc-list",  # apple x11
        "/usr/X11R6/bin/fc-list",  # apple x11
    ]
    for bin_location in fclist_locations:
        if exists(bin_location):
            fonts = initsysfonts_unix(bin_location)
            break

    if len(fonts) == 0:
        fonts = _font_finder_darwin()

    return fonts


# read the fonts on unix
def initsysfonts_unix(path="fc-list"):
    """use the fc-list from fontconfig to get a list of fonts"""
    fonts = {}

    if sys.platform == "emscripten":
        return fonts

    try:
        proc = subprocess.run(
            [path, ":", "file", "family", "style"],
            stdout=subprocess.PIPE,  # capture stdout
            stderr=subprocess.PIPE,  # capture stderr
            check=True,  # so that errors raise python exception which is handled below
            timeout=1,  # so that we don't hang the program waiting
        )

    except FileNotFoundError:
        warnings.warn(
            f"'{path}' is missing, system fonts cannot be loaded on your platform"
        )

    except subprocess.TimeoutExpired:
        warnings.warn(
            f"Process running '{path}' timed-out! System fonts cannot be loaded on "
            "your platform"
        )

    except subprocess.CalledProcessError as e:
        warnings.warn(
            f"'{path}' failed with error code {e.returncode}! System fonts cannot be "
            f"loaded on your platform. Error log is:\n{e.stderr}"
        )

    else:
        for entry in proc.stdout.decode("ascii", "ignore").splitlines():
            try:
                _parse_font_entry_unix(entry, fonts)
            except ValueError:
                # try the next one.
                pass

    return fonts


def _parse_font_entry_unix(entry, fonts):
    """
    Parses an entry in the unix font data to add to the pygame font
    dictionary.

    :param entry: A entry from the unix font list.
    :param fonts: The pygame font dictionary to add the parsed font data to.

    """
    filename, family, style = entry.split(":", 2)
    if splitext(filename)[1].lower() in OpenType_extensions:
        bold = "Bold" in style
        italic = "Italic" in style
        oblique = "Oblique" in style
        for name in family.strip().split(","):
            if name:
                break
        else:
            name = splitext(basename(filename))[0]

        _addfont(_simplename(name), bold, italic or oblique, filename, fonts)


def create_aliases():
    """Map common fonts that are absent from the system to similar fonts
    that are installed in the system
    """
    alias_groups = (
        (
            "monospace",
            "misc-fixed",
            "courier",
            "couriernew",
            "console",
            "fixed",
            "mono",
            "freemono",
            "bitstreamverasansmono",
            "verasansmono",
            "monotype",
            "lucidaconsole",
            "consolas",
            "dejavusansmono",
            "liberationmono",
        ),
        (
            "sans",
            "arial",
            "helvetica",
            "swiss",
            "freesans",
            "bitstreamverasans",
            "verasans",
            "verdana",
            "tahoma",
            "calibri",
            "gillsans",
            "segoeui",
            "trebuchetms",
            "ubuntu",
            "dejavusans",
            "liberationsans",
        ),
        (
            "serif",
            "times",
            "freeserif",
            "bitstreamveraserif",
            "roman",
            "timesroman",
            "timesnewroman",
            "dutch",
            "veraserif",
            "georgia",
            "cambria",
            "constantia",
            "dejavuserif",
            "liberationserif",
        ),
        ("wingdings", "wingbats"),
        ("comicsansms", "comicsans"),
    )
    for alias_set in alias_groups:
        for name in alias_set:
            if name in Sysfonts:
                found = Sysfonts[name]
                break
        else:
            continue
        for name in alias_set:
            if name not in Sysfonts:
                Sysalias[name] = found


def initsysfonts():
    """
    Initialise the sysfont module, called once. Locates the installed fonts
    and creates some aliases for common font categories.

    Has different initialisation functions for different platforms.
    """
    global is_init
    if is_init:
        # no need to re-init
        return

    if sys.platform == "win32":
        fonts = initsysfonts_win32()
    elif sys.platform == "darwin":
        fonts = initsysfonts_darwin()
    else:
        fonts = initsysfonts_unix()

    Sysfonts.update(fonts)
    create_aliases()
    is_init = True


def font_constructor(fontpath, size, bold, italic):
    """
    pygame.font specific declarations

    :param fontpath: path to a font.
    :param size: size of a font.
    :param bold: bold style, True or False.
    :param italic: italic style, True or False.

    :return: A font.Font object.
    """

    font = Font(fontpath, size)
    if bold:
        font.set_bold(True)
    if italic:
        font.set_italic(True)

    return font


# the exported functions


def SysFont(name, size, bold=False, italic=False, constructor=None):
    """pygame.font.SysFont(name, size, bold=False, italic=False, constructor=None) -> Font
    Create a pygame Font from system font resources.

    This will search the system fonts for the given font
    name. You can also enable bold or italic styles, and
    the appropriate system font will be selected if available.

    This will always return a valid Font object, and will
    fallback on the builtin pygame font if the given font
    is not found.

    Name can also be an iterable of font names, a string of
    comma-separated font names, or a bytes of comma-separated
    font names, in which case the set of names will be searched
    in order. Pygame uses a small set of common font aliases. If the
    specific font you ask for is not available, a reasonable
    alternative may be used.

    If optional constructor is provided, it must be a function with
    signature constructor(fontpath, size, bold, italic) which returns
    a Font instance. If None, a pygame.font.Font object is created.
    """
    if constructor is None:
        constructor = font_constructor

    initsysfonts()

    gotbold = gotitalic = False
    fontname = None
    if name:
        if isinstance(name, (str, bytes)):
            name = name.split(b"," if isinstance(name, bytes) else ",")
        for single_name in name:
            if isinstance(single_name, bytes):
                single_name = single_name.decode()

            single_name = _simplename(single_name)
            styles = Sysfonts.get(single_name)
            if not styles:
                styles = Sysalias.get(single_name)
            if styles:
                plainname = styles.get((False, False))
                fontname = styles.get((bold, italic))
                if not (fontname or plainname):
                    # Neither requested style, nor plain font exists, so
                    # return a font with the name requested, but an
                    # arbitrary style.
                    (style, fontname) = list(styles.items())[0]
                    # Attempt to style it as requested. This can't
                    # unbold or unitalicize anything, but it can
                    # fake bold and/or fake italicize.
                    if bold and style[0]:
                        gotbold = True
                    if italic and style[1]:
                        gotitalic = True
                elif not fontname:
                    fontname = plainname
                elif plainname != fontname:
                    gotbold = bold
                    gotitalic = italic
            if fontname:
                break

    set_bold = set_italic = False
    if bold and not gotbold:
        set_bold = True
    if italic and not gotitalic:
        set_italic = True

    return constructor(fontname, size, set_bold, set_italic)


def get_fonts():
    """pygame.font.get_fonts() -> list
    get a list of system font names

    Returns the list of all found system fonts. Note that
    the names of the fonts will be all lowercase with spaces
    removed. This is how pygame internally stores the font
    names for matching.
    """
    initsysfonts()
    return list(Sysfonts)


def match_font(name, bold=False, italic=False):
    """pygame.font.match_font(name, bold=0, italic=0) -> name
    find the filename for the named system font

    This performs the same font search as the SysFont()
    function, only it returns the path to the TTF file
    that would be loaded. The font name can also be an
    iterable of font names or a string/bytes of comma-separated
    font names to try.

    If no match is found, None is returned.
    """
    initsysfonts()

    fontname = None
    if isinstance(name, (str, bytes)):
        name = name.split(b"," if isinstance(name, bytes) else ",")

    for single_name in name:
        if isinstance(single_name, bytes):
            single_name = single_name.decode()

        single_name = _simplename(single_name)
        styles = Sysfonts.get(single_name)
        if not styles:
            styles = Sysalias.get(single_name)
        if styles:
            while not fontname:
                fontname = styles.get((bold, italic))
                if italic:
                    italic = 0
                elif bold:
                    bold = 0
                elif not fontname:
                    fontname = list(styles.values())[0]

        if fontname:
            break

    return fontname
