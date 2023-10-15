/*
    pygame - Python Game Library
    Copyright (C) 2000-2001  Pete Shinners

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

    Pete Shinners
    pete@shinners.org
*/

#include <Python.h>
#include "pgplatform.h"

struct TTF_Font;

typedef struct {
    PyObject_HEAD TTF_Font *font;
    PyObject *weakreflist;
    unsigned int ttf_init_generation;
} PyFontObject;
#define PyFont_AsFont(x) (((PyFontObject *)x)->font)

#ifndef PYGAMEAPI_FONT_INTERNAL

#include "pgimport.h"

PYGAMEAPI_DEFINE_SLOTS(font);

#define PyFont_Type (*(PyTypeObject *)PYGAMEAPI_GET_SLOT(font, 0))
#define PyFont_Check(x) ((x)->ob_type == &PyFont_Type)

#define PyFont_New (*(PyObject * (*)(TTF_Font *)) PYGAMEAPI_GET_SLOT(font, 1))

/*slot 2 taken by FONT_INIT_CHECK*/

#define import_pygame_font() _IMPORT_PYGAME_MODULE(font)

#endif
