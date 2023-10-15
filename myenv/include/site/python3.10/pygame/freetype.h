/*
  pygame - Python Game Library
  Copyright (C) 2009 Vicent Marti

  This library is free software; you can redistribute it and/or
  modify it under the terms of the GNU Library General Public
  License as published by the Free Software Foundation; either
  version 2 of the License, or (at your option) any later version.

  This library is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  Library General Public License for more details.

  You should have received a copy of the GNU Library General Public
  License along with this library; if not, write to the Free
  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

*/
#ifndef _PYGAME_FREETYPE_INTERNAL_H_
#define _PYGAME_FREETYPE_INTERNAL_H_

#include "pgcompat.h"
#include "pgplatform.h"

#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_CACHE_H
#include FT_XFREE86_H
#include FT_TRIGONOMETRY_H

/**********************************************************
 * Global module constants
 **********************************************************/

/* Render styles */
#define FT_STYLE_NORMAL 0x00
#define FT_STYLE_STRONG 0x01
#define FT_STYLE_OBLIQUE 0x02
#define FT_STYLE_UNDERLINE 0x04
#define FT_STYLE_WIDE 0x08
#define FT_STYLE_DEFAULT 0xFF

/* Bounding box modes */
#define FT_BBOX_EXACT FT_GLYPH_BBOX_SUBPIXELS
#define FT_BBOX_EXACT_GRIDFIT FT_GLYPH_BBOX_GRIDFIT
#define FT_BBOX_PIXEL FT_GLYPH_BBOX_TRUNCATE
#define FT_BBOX_PIXEL_GRIDFIT FT_GLYPH_BBOX_PIXELS

/* Rendering flags */
#define FT_RFLAG_NONE (0)
#define FT_RFLAG_ANTIALIAS (1 << 0)
#define FT_RFLAG_AUTOHINT (1 << 1)
#define FT_RFLAG_VERTICAL (1 << 2)
#define FT_RFLAG_HINTED (1 << 3)
#define FT_RFLAG_KERNING (1 << 4)
#define FT_RFLAG_TRANSFORM (1 << 5)
#define FT_RFLAG_PAD (1 << 6)
#define FT_RFLAG_ORIGIN (1 << 7)
#define FT_RFLAG_UCS4 (1 << 8)
#define FT_RFLAG_USE_BITMAP_STRIKES (1 << 9)
#define FT_RFLAG_DEFAULTS \
    (FT_RFLAG_HINTED | FT_RFLAG_USE_BITMAP_STRIKES | FT_RFLAG_ANTIALIAS)

#define FT_RENDER_NEWBYTEARRAY 0x0
#define FT_RENDER_NEWSURFACE 0x1
#define FT_RENDER_EXISTINGSURFACE 0x2

/**********************************************************
 * Global module types
 **********************************************************/

typedef struct _scale_s {
    FT_UInt x, y;
} Scale_t;
typedef FT_Angle Angle_t;

struct fontinternals_;
struct freetypeinstance_;

typedef struct {
    FT_Long font_index;
    FT_Open_Args open_args;
} pgFontId;

typedef struct {
    PyObject_HEAD pgFontId id;
    PyObject *path;
    int is_scalable;
    int is_bg_col_set;

    Scale_t face_size;
    FT_Int16 style;
    FT_Int16 render_flags;
    double strength;
    double underline_adjustment;
    FT_UInt resolution;
    Angle_t rotation;
    FT_Matrix transform;
    FT_Byte fgcolor[4];
    FT_Byte bgcolor[4];

    struct freetypeinstance_ *freetype; /* Personal reference */
    struct fontinternals_ *_internals;
} pgFontObject;

#define pgFont_IS_ALIVE(o) (((pgFontObject *)(o))->_internals != 0)

/* import public API */
#include "include/pygame_freetype.h"

#define PYGAMEAPI_FREETYPE_NUMSLOTS 2

#endif /* ~_PYGAME_FREETYPE_INTERNAL_H_ */
