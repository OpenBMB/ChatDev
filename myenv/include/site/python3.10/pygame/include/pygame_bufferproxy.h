/*
  pygame - Python Game Library
  Copyright (C) 2000-2001  Pete Shinners
  Copyright (C) 2007  Rene Dudfield, Richard Goedeken

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

/* Bufferproxy module C api. */
#if !defined(PG_BUFPROXY_HEADER)
#define PG_BUFPROXY_HEADER

#include <Python.h>

typedef PyObject *(*_pgbufproxy_new_t)(PyObject *, getbufferproc);
typedef PyObject *(*_pgbufproxy_get_obj_t)(PyObject *);
typedef int (*_pgbufproxy_trip_t)(PyObject *);

#ifndef PYGAMEAPI_BUFPROXY_INTERNAL

#include "pgimport.h"

PYGAMEAPI_DEFINE_SLOTS(bufferproxy);

#define pgBufproxy_Type (*(PyTypeObject *)PYGAMEAPI_GET_SLOT(bufferproxy, 0))

#define pgBufproxy_Check(x) ((x)->ob_type == &pgBufproxy_Type)

#define pgBufproxy_New (*(_pgbufproxy_new_t)PYGAMEAPI_GET_SLOT(bufferproxy, 1))

#define pgBufproxy_GetParent \
    (*(_pgbufproxy_get_obj_t)PYGAMEAPI_GET_SLOT(bufferproxy, 2))

#define pgBufproxy_Trip \
    (*(_pgbufproxy_trip_t)PYGAMEAPI_GET_SLOT(bufferproxy, 3))

#define import_pygame_bufferproxy() _IMPORT_PYGAME_MODULE(bufferproxy)

#endif /* ~PYGAMEAPI_BUFPROXY_INTERNAL */

#endif /* ~defined(PG_BUFPROXY_HEADER) */
