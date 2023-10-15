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

#ifndef PGMIXER_H
#define PGMIXER_H

#include <Python.h>
#include <structmember.h>

#include "pgcompat.h"

struct Mix_Chunk;

typedef struct {
    PyObject_HEAD Mix_Chunk *chunk;
    Uint8 *mem;
    PyObject *weakreflist;
} pgSoundObject;

typedef struct {
    PyObject_HEAD int chan;
} pgChannelObject;

#define pgSound_AsChunk(x) (((pgSoundObject *)x)->chunk)
#define pgChannel_AsInt(x) (((pgChannelObject *)x)->chan)

#include "pgimport.h"

#ifndef PYGAMEAPI_MIXER_INTERNAL

PYGAMEAPI_DEFINE_SLOTS(mixer);

#define pgSound_Type (*(PyTypeObject *)PYGAMEAPI_GET_SLOT(mixer, 0))

#define pgSound_Check(x) ((x)->ob_type == &pgSound_Type)

#define pgSound_New \
    (*(PyObject * (*)(Mix_Chunk *)) PYGAMEAPI_GET_SLOT(mixer, 1))

#define pgSound_Play \
    (*(PyObject * (*)(PyObject *, PyObject *)) PYGAMEAPI_GET_SLOT(mixer, 2))

#define pgChannel_Type (*(PyTypeObject *)PYGAMEAPI_GET_SLOT(mixer, 3))
#define pgChannel_Check(x) ((x)->ob_type == &pgChannel_Type)

#define pgChannel_New (*(PyObject * (*)(int)) PYGAMEAPI_GET_SLOT(mixer, 4))

#define import_pygame_mixer() _IMPORT_PYGAME_MODULE(mixer)

#endif /* PYGAMEAPI_MIXER_INTERNAL */

#endif /* ~PGMIXER_H */
