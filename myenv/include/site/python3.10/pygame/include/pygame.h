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

/* To allow the Pygame C api to be globally shared by all code within an
 * extension module built from multiple C files,  only include the pygame.h
 * header within the top level C file, the one which calls the
 * 'import_pygame_*' macros. All other C source files of the module should
 * include _pygame.h instead.
 */
#ifndef PYGAME_H
#define PYGAME_H

#include "_pygame.h"

#endif
