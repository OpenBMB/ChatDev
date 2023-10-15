/*
    pygame - Python Game Library
    Copyright (C) 2006, 2007 Rene Dudfield, Marcus von Appen

    Originally put in the public domain by Sam Lantinga.

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

#ifndef SCRAP_H
#define SCRAP_H

/* This is unconditionally defined in Python.h */
#if defined(_POSIX_C_SOURCE)
#undef _POSIX_C_SOURCE
#endif

#include <Python.h>

/* Handle clipboard text and data in arbitrary formats */

/**
 * Predefined supported pygame scrap types.
 */
#define PYGAME_SCRAP_TEXT "text/plain"
#define PYGAME_SCRAP_BMP "image/bmp"
#define PYGAME_SCRAP_PPM "image/ppm"
#define PYGAME_SCRAP_PBM "image/pbm"

/**
 * The supported scrap clipboard types.
 *
 * This is only relevant in a X11 environment, which supports mouse
 * selections as well. For Win32 and MacOS environments the default
 * clipboard is used, no matter what value is passed.
 */
typedef enum {
    SCRAP_CLIPBOARD,
    SCRAP_SELECTION /* only supported in X11 environments. */
} ScrapClipType;

/**
 * Macro for initialization checks.
 */
#define PYGAME_SCRAP_INIT_CHECK()                                             \
    if (!pygame_scrap_initialized())                                          \
    return (PyErr_SetString(pgExc_SDLError, "scrap system not initialized."), \
            NULL)

/**
 * \brief Checks, whether the pygame scrap module was initialized.
 *
 * \return 1 if the modules was initialized, 0 otherwise.
 */
extern int
pygame_scrap_initialized(void);

/**
 * \brief Initializes the pygame scrap module internals. Call this before any
 *        other method.
 *
 * \return 1 on successful initialization, 0 otherwise.
 */
extern int
pygame_scrap_init(void);

/**
 * \brief Checks, whether the pygame window lost the clipboard focus or not.
 *
 * \return 1 if the window lost the focus, 0 otherwise.
 */
extern int
pygame_scrap_lost(void);

/**
 * \brief Places content of a specific type into the clipboard.
 *
 * \note For X11 the following notes are important: The following types
 *       are reserved for internal usage and thus will throw an error on
 *       setting them: "TIMESTAMP", "TARGETS", "SDL_SELECTION".
 *       Setting PYGAME_SCRAP_TEXT ("text/plain") will also automatically
 *       set the X11 types "STRING" (XA_STRING), "TEXT" and "UTF8_STRING".
 *
 *       For Win32 the following notes are important: Setting
 *       PYGAME_SCRAP_TEXT ("text/plain") will also automatically set
 *       the Win32 type "TEXT" (CF_TEXT).
 *
 *       For QNX the following notes are important: Setting
 *       PYGAME_SCRAP_TEXT ("text/plain") will also automatically set
 *       the QNX type "TEXT" (Ph_CL_TEXT).
 *
 * \param type The type of the content.
 * \param srclen The length of the content.
 * \param src The NULL terminated content.
 * \return 1, if the content could be successfully pasted into the clipboard,
 *         0 otherwise.
 */
extern int
pygame_scrap_put(char *type, Py_ssize_t srclen, char *src);

/**
 * \brief Gets the current content from the clipboard.
 *
 * \note The received content does not need to be the content previously
 *       placed in the clipboard using pygame_put_scrap(). See the
 *       pygame_put_scrap() notes for more details.
 *
 * \param type The type of the content to receive.
 * \param count The size of the returned content.
 * \return The content or NULL in case of an error or if no content of the
 *         specified type was available.
 */
extern char *
pygame_scrap_get(char *type, size_t *count);

/**
 * \brief Gets the currently available content types from the clipboard.
 *
 * \return The different available content types or NULL in case of an
 *         error or if no content type is available.
 */
extern char **
pygame_scrap_get_types(void);

/**
 * \brief Checks whether content for the specified scrap type is currently
 * available in the clipboard.
 *
 * \param type The type to check for.
 * \return 1, if there is content and 0 otherwise.
 */
extern int
pygame_scrap_contains(char *type);

#endif /* SCRAP_H */
