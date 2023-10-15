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
#ifndef PYGAME_FREETYPE_H_
#define PYGAME_FREETYPE_H_

#include "pgplatform.h"
#include "pgimport.h"
#include "pgcompat.h"

#ifndef PYGAME_FREETYPE_INTERNAL

PYGAMEAPI_DEFINE_SLOTS(_freetype);

#define pgFont_Type (*(PyTypeObject *)PYGAMEAPI_GET_SLOT(_freetype, 0))

#define pgFont_Check(x) ((x)->ob_type == &pgFont_Type)

#define pgFont_New \
    (*(PyObject * (*)(const char *, long)) PYGAMEAPI_GET_SLOT(_freetype, 1))

#define import_pygame_freetype() _IMPORT_PYGAME_MODULE(_freetype)

#endif /* PYGAME_FREETYPE_INTERNAL */

#endif /* PYGAME_FREETYPE_H_ */
