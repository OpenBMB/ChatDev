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

#ifndef _PYGAME_H
#define _PYGAME_H

/** This header file includes all the definitions for the
 ** base pygame extensions. This header only requires
 ** Python includes (and SDL.h for functions that use SDL types).
 ** The reason for functions prototyped with #define's is
 ** to allow for maximum Python portability. It also uses
 ** Python as the runtime linker, which allows for late binding.
 '' For more information on this style of development, read
 ** the Python docs on this subject.
 ** http://www.python.org/doc/current/ext/using-cobjects.html
 **
 ** If using this to build your own derived extensions,
 ** you'll see that the functions available here are mainly
 ** used to help convert between python objects and SDL objects.
 ** Since this library doesn't add a lot of functionality to
 ** the SDL library, it doesn't need to offer a lot either.
 **
 ** When initializing your extension module, you must manually
 ** import the modules you want to use. (this is the part about
 ** using python as the runtime linker). Each module has its
 ** own import_xxx() routine. You need to perform this import
 ** after you have initialized your own module, and before
 ** you call any routines from that module. Since every module
 ** in pygame does this, there are plenty of examples.
 **
 ** The base module does include some useful conversion routines
 ** that you are free to use in your own extension.
 **/

#include "pgplatform.h"
#include <Python.h>

/* version macros (defined since version 1.9.5) */
#define PG_MAJOR_VERSION 2
#define PG_MINOR_VERSION 5
#define PG_PATCH_VERSION 1
#define PG_VERSIONNUM(MAJOR, MINOR, PATCH) \
    (1000 * (MAJOR) + 100 * (MINOR) + (PATCH))
#define PG_VERSION_ATLEAST(MAJOR, MINOR, PATCH)                             \
    (PG_VERSIONNUM(PG_MAJOR_VERSION, PG_MINOR_VERSION, PG_PATCH_VERSION) >= \
     PG_VERSIONNUM(MAJOR, MINOR, PATCH))

#include "pgcompat.h"

/* Flag indicating a pg_buffer; used for assertions within callbacks */
#ifndef NDEBUG
#define PyBUF_PYGAME 0x4000
#endif
#define PyBUF_HAS_FLAG(f, F) (((f) & (F)) == (F))

/* Array information exchange struct C type; inherits from Py_buffer
 *
 * Pygame uses its own Py_buffer derived C struct as an internal representation
 * of an imported array buffer. The extended Py_buffer allows for a
 * per-instance release callback,
 */
typedef void (*pybuffer_releaseproc)(Py_buffer *);

typedef struct pg_bufferinfo_s {
    Py_buffer view;
    PyObject *consumer; /* Input: Borrowed reference */
    pybuffer_releaseproc release_buffer;
} pg_buffer;

#include "pgimport.h"

/*
 * BASE module
 */
#ifndef PYGAMEAPI_BASE_INTERNAL
#define pgExc_SDLError ((PyObject *)PYGAMEAPI_GET_SLOT(base, 0))

#define pg_RegisterQuit \
    (*(void (*)(void (*)(void)))PYGAMEAPI_GET_SLOT(base, 1))

/**
 * \brief Convert number like object *obj* to C int and in *val*.
 *
 * \param obj The Python object to convert.
 * \param val A pointer to the C integer to store the result.
 * \returns 1 if the conversion was successful, 0 otherwise.
 *
 * \note This function will clear any Python errors.
 * \note This function will convert floats to integers.
 */
#define pg_IntFromObj \
    (*(int (*)(PyObject *, int *))PYGAMEAPI_GET_SLOT(base, 2))

/**
 * \brief Convert number like object at position *i* in sequence *obj*
 * to C int and place in argument *val*.
 *
 * \param obj The Python object to convert.
 * \param i The index of the object to convert.
 * \param val A pointer to the C integer to store the result.
 * \returns 1 if the conversion was successful, 0 otherwise.
 *
 * \note This function will clear any Python errors.
 * \note This function will convert floats to integers.
 */
#define pg_IntFromObjIndex \
    (*(int (*)(PyObject *, int, int *))PYGAMEAPI_GET_SLOT(base, 3))

/**
 * \brief Convert the two number like objects in length 2 sequence *obj* to C
 * int and place in arguments *val1* and *val2*.
 *
 * \param obj The Python two element sequence object to convert.
 * \param val A pointer to the C integer to store the result.
 * \param val2 A pointer to the C integer to store the result.
 * \returns 1 if the conversion was successful, 0 otherwise.
 *
 * \note This function will clear any Python errors.
 * \note This function will convert floats to integers.
 */
#define pg_TwoIntsFromObj \
    (*(int (*)(PyObject *, int *, int *))PYGAMEAPI_GET_SLOT(base, 4))

/**
 * \brief Convert number like object *obj* to C float and in *val*.
 *
 * \param obj The Python object to convert.
 * \param val A pointer to the C float to store the result.
 * \returns 1 if the conversion was successful, 0 otherwise.
 *
 * \note This function will clear any Python errors.
 */
#define pg_FloatFromObj \
    (*(int (*)(PyObject *, float *))PYGAMEAPI_GET_SLOT(base, 5))

/**
 * \brief Convert number like object at position *i* in sequence *obj* to C
 * float and place in argument *val*.
 *
 * \param obj The Python object to convert.
 * \param i The index of the object to convert.
 * \param val A pointer to the C float to store the result.
 * \returns 1 if the conversion was successful, 0 otherwise.
 *
 * \note This function will clear any Python errors.
 */
#define pg_FloatFromObjIndex \
    (*(int (*)(PyObject *, int, float *))PYGAMEAPI_GET_SLOT(base, 6))

/**
 * \brief Convert the two number like objects in length 2 sequence *obj* to C
 * float and place in arguments *val1* and *val2*.
 *
 * \param obj The Python two element sequence object to convert.
 * \param val A pointer to the C float to store the result.
 * \param val2 A pointer to the C float to store the result.
 * \returns 1 if the conversion was successful, 0 otherwise.
 *
 * \note This function will clear any Python errors.
 */
#define pg_TwoFloatsFromObj \
    (*(int (*)(PyObject *, float *, float *))PYGAMEAPI_GET_SLOT(base, 7))

/**
 * \brief Convert number like object *obj* to C Uint32 and in *val*.
 *
 * \param obj The Python object to convert.
 * \param val A pointer to the C int to store the result.
 * \returns 1 if the conversion was successful, 0 otherwise.
 */
#define pg_UintFromObj \
    (*(int (*)(PyObject *, Uint32 *))PYGAMEAPI_GET_SLOT(base, 8))

/**
 * \brief Convert number like object at position *i* in sequence *obj* to C
 * Uint32 and place in argument *val*.
 *
 * \param obj The Python object to convert.
 * \param i The index of the object to convert.
 * \param val A pointer to the C int to store the result.
 * \returns 1 if the conversion was successful, 0 otherwise.
 */
#define pg_UintFromObjIndex \
    (*(int (*)(PyObject *, int, Uint32 *))PYGAMEAPI_GET_SLOT(base, 9))

/**
 * \brief Initialize all of the pygame modules.
 * \returns 1 on success, 0 on failure with PyErr set.
 */
#define pg_mod_autoinit (*(int (*)(const char *))PYGAMEAPI_GET_SLOT(base, 10))

/**
 * \brief Quit all of the pygame modules.
 */
#define pg_mod_autoquit (*(void (*)(const char *))PYGAMEAPI_GET_SLOT(base, 11))

/**
 * \brief Convert the color represented by object *obj* into a red, green,
 * blue, alpha length 4 C array *RGBA*.
 *
 * The object must be a length 3 or 4 sequence of numbers having values between
 * 0 and 255 inclusive. For a length 3 sequence an alpha value of 255 is
 * assumed.
 *
 * \param obj The Python object to convert.
 * \param RGBA A pointer to the C array to store the result.
 * \returns 1 if the conversion was successful, 0 otherwise.
 */
#define pg_RGBAFromObj \
    (*(int (*)(PyObject *, Uint8 *))PYGAMEAPI_GET_SLOT(base, 12))

/**
 * \brief Given a Py_buffer, return a python dictionary representing the array
 * interface.
 *
 * \param view_p A pointer to the Py_buffer to convert to a dictionary.
 *
 * \returns A Python dictionary representing the array interface of the object.
 */
#define pgBuffer_AsArrayInterface \
    (*(PyObject * (*)(Py_buffer *)) PYGAMEAPI_GET_SLOT(base, 13))

/**
 * \brief Given a Py_buffer, return a python capsule representing the array
 * interface.
 *
 * \param view_p A pointer to the Py_buffer to convert to a capsule.
 *
 * \returns A Python capsule representing the array interface of the object.
 */
#define pgBuffer_AsArrayStruct \
    (*(PyObject * (*)(Py_buffer *)) PYGAMEAPI_GET_SLOT(base, 14))

/**
 * \brief Get a buffer object from a given Python object.
 *
 * \param obj The Python object to get the buffer from.
 * \param pg_view_p A pointer to a pg_buffer struct to store the buffer in.
 * \param flags The desired buffer access mode.
 *
 * \returns 0 on success, -1 on failure.
 *
 * \note This function attempts to get a buffer object from a given Python
 * object. If the object supports the buffer protocol, it will be used to
 * create the buffer. If not, it will try to get an array interface or
 * dictionary representation of the object and use that to create the buffer.
 * If none of these methods work, it will raise a ValueError.
 *
 */
#define pgObject_GetBuffer \
    (*(int (*)(PyObject *, pg_buffer *, int))PYGAMEAPI_GET_SLOT(base, 15))

/**
 * \brief Release a pg_buffer object.
 *
 * \param pg_view_p The pg_buffer object to release.
 *
 * \note This function releases a pg_buffer object.
 * \note some calls to this function expect this function to not clear
 * previously set errors.
 */
#define pgBuffer_Release (*(void (*)(pg_buffer *))PYGAMEAPI_GET_SLOT(base, 16))

/**
 * \brief Write the array interface dictionary buffer description *dict* into a
 * Pygame buffer description struct *pg_view_p*.
 *
 * \param pg_view_p The Pygame buffer description struct to write into.
 * \param dict The array interface dictionary to read from.
 * \param flags The PyBUF flags describing the view type requested.
 *
 * \returns 0 on success, or -1 on failure.
 */
#define pgDict_AsBuffer \
    (*(int (*)(pg_buffer *, PyObject *, int))PYGAMEAPI_GET_SLOT(base, 17))

#define pgExc_BufferError ((PyObject *)PYGAMEAPI_GET_SLOT(base, 18))

/**
 * \brief Get the default SDL window created by a pygame.display.set_mode()
 * call, or *NULL*.
 *
 * \return The default window, or *NULL* if no window has been created.
 */
#define pg_GetDefaultWindow \
    (*(SDL_Window * (*)(void)) PYGAMEAPI_GET_SLOT(base, 19))

/**
 * \brief Set the default SDL window created by a pygame.display.set_mode()
 * call. The previous window, if any, is destroyed. Argument *win* may be
 * *NULL*. This function is called by pygame.display.set_mode().
 *
 * \param win The new default window. May be NULL.
 */
#define pg_SetDefaultWindow \
    (*(void (*)(SDL_Window *))PYGAMEAPI_GET_SLOT(base, 20))

/**
 * \brief Return a borrowed reference to the Pygame default window display
 * surface, or *NULL* if no default window is open.
 *
 * \return The default renderer, or *NULL* if no renderer has been created.
 */
#define pg_GetDefaultWindowSurface \
    (*(pgSurfaceObject * (*)(void)) PYGAMEAPI_GET_SLOT(base, 21))

/**
 * \brief Set the Pygame default window display surface. The previous
 * surface, if any, is destroyed. Argument *screen* may be *NULL*. This
 * function is called by pygame.display.set_mode().
 *
 * \param screen The new default window display surface. May be NULL.
 */
#define pg_SetDefaultWindowSurface \
    (*(void (*)(pgSurfaceObject *))PYGAMEAPI_GET_SLOT(base, 22))

/**
 * \returns NULL if the environment variable PYGAME_BLEND_ALPHA_SDL2 is not
 * set, otherwise returns a pointer to the environment variable.
 */
#define pg_EnvShouldBlendAlphaSDL2 \
    (*(char *(*)(void))PYGAMEAPI_GET_SLOT(base, 23))

/**
 * \brief Convert number like object *obj* to C double and in *val*.
 *
 * \param obj The Python object to convert.
 * \param val A pointer to the C double to store the result.
 * \returns 1 if the conversion was successful, 0 otherwise.
 *
 * \note This function will clear any Python errors.
 */
#define pg_DoubleFromObj \
    (*(int (*)(PyObject *, double *))PYGAMEAPI_GET_SLOT(base, 24))

/**
 * \brief Convert number like object at position *i* in sequence *obj* to C
 * double and place in argument *val*.
 *
 * \param obj The Python object to convert.
 * \param i The index of the object to convert.
 * \param val A pointer to the C double to store the result.
 * \returns 1 if the conversion was successful, 0 otherwise.
 *
 * \note This function will clear any Python errors.
 */
#define pg_DoubleFromObjIndex \
    (*(int (*)(PyObject *, int, double *))PYGAMEAPI_GET_SLOT(base, 25))

/**
 * \brief Convert the two number like objects in length 2 sequence *obj* to C
 * double and place in arguments *val1* and *val2*.
 *
 * \param obj The Python two element sequence object to convert.
 * \param val A pointer to the C double to store the result.
 * \param val2 A pointer to the C double to store the result.
 * \returns 1 if the conversion was successful, 0 otherwise.
 */
#define pg_TwoDoublesFromObj \
    (*(int (*)(PyObject *, double *, double *))PYGAMEAPI_GET_SLOT(base, 26))

#define import_pygame_base() IMPORT_PYGAME_MODULE(base)
#endif /* ~PYGAMEAPI_BASE_INTERNAL */

typedef struct {
    PyObject_HEAD SDL_Rect r;
    PyObject *weakreflist;
} pgRectObject;

#define pgRect_AsRect(x) (((pgRectObject *)x)->r)
#ifndef PYGAMEAPI_RECT_INTERNAL
#define pgRect_Type (*(PyTypeObject *)PYGAMEAPI_GET_SLOT(rect, 0))

#define pgRect_Check(x) ((x)->ob_type == &pgRect_Type)
#define pgRect_New (*(PyObject * (*)(SDL_Rect *)) PYGAMEAPI_GET_SLOT(rect, 1))

#define pgRect_New4 \
    (*(PyObject * (*)(int, int, int, int)) PYGAMEAPI_GET_SLOT(rect, 2))

#define pgRect_FromObject \
    (*(SDL_Rect * (*)(PyObject *, SDL_Rect *)) PYGAMEAPI_GET_SLOT(rect, 3))

#define pgRect_Normalize (*(void (*)(SDL_Rect *))PYGAMEAPI_GET_SLOT(rect, 4))

#define import_pygame_rect() IMPORT_PYGAME_MODULE(rect)
#endif /* ~PYGAMEAPI_RECT_INTERNAL */

/*
 * JOYSTICK module
 */
typedef struct pgJoystickObject {
    PyObject_HEAD int id;
    SDL_Joystick *joy;

    /* Joysticks form an intrusive linked list.
     *
     * Note that we don't maintain refcounts for these so they are weakrefs
     * from the Python side.
     */
    struct pgJoystickObject *next;
    struct pgJoystickObject *prev;
} pgJoystickObject;

#define pgJoystick_AsID(x) (((pgJoystickObject *)x)->id)
#define pgJoystick_AsSDL(x) (((pgJoystickObject *)x)->joy)

#ifndef PYGAMEAPI_JOYSTICK_INTERNAL
#define pgJoystick_Type (*(PyTypeObject *)PYGAMEAPI_GET_SLOT(joystick, 0))

#define pgJoystick_Check(x) ((x)->ob_type == &pgJoystick_Type)
#define pgJoystick_New (*(PyObject * (*)(int)) PYGAMEAPI_GET_SLOT(joystick, 1))

#define import_pygame_joystick() IMPORT_PYGAME_MODULE(joystick)
#endif

/*
 * DISPLAY module
 */

typedef struct {
    Uint32 hw_available : 1;
    Uint32 wm_available : 1;
    Uint32 blit_hw : 1;
    Uint32 blit_hw_CC : 1;
    Uint32 blit_hw_A : 1;
    Uint32 blit_sw : 1;
    Uint32 blit_sw_CC : 1;
    Uint32 blit_sw_A : 1;
    Uint32 blit_fill : 1;
    Uint32 video_mem;
    SDL_PixelFormat *vfmt;
    SDL_PixelFormat vfmt_data;
    int current_w;
    int current_h;
} pg_VideoInfo;

/**
 * A pygame object that wraps an SDL_VideoInfo struct.
 * The object returned by `pygame.display.Info()`
 */
typedef struct {
    PyObject_HEAD pg_VideoInfo info;
} pgVidInfoObject;

/**
 * \brief Convert a pgVidInfoObject to an SDL_VideoInfo.
 *
 * \note SDL_VideoInfo pgVidInfo_AsVidInfo(PyObject *obj)
 *
 * \returns the SDL_VideoInfo field of *obj*, a pgVidInfo_Type instance.
 * \param obj A pgVidInfo_Type instance.
 *
 * \note Does not check that *obj* is not `NULL` or an `pgVidInfoObject`
 * object.
 */
#define pgVidInfo_AsVidInfo(x) (((pgVidInfoObject *)x)->info)

#ifndef PYGAMEAPI_DISPLAY_INTERNAL
/**
 * \brief The pgVidInfoObject object Python type.
 * \note pgVideoInfo_Type is used for the `pygame.display.Info()` object.
 */
#define pgVidInfo_Type (*(PyTypeObject *)PYGAMEAPI_GET_SLOT(display, 0))

/**
 * \brief Check if *obj* is a pgVidInfoObject.
 *
 * \returns true if *x* is a `pgVidInfo_Type` instance
 * \note Will return false if *x* is a subclass of `pgVidInfo_Type`.
 * \note This macro does not check that *x* is not ``NULL``.
 * \note int pgVidInfo_Check(PyObject *x)
 */
#define pgVidInfo_Check(x) ((x)->ob_type == &pgVidInfo_Type)

/**
 * \brief Create a new pgVidInfoObject.
 *
 * \param i A pointer to an SDL_VideoInfo struct.
 * \returns a new `pgVidInfoObject` object for the SDL_VideoInfo *i*.
 *
 * \note PyObject* pgVidInfo_New(SDL_VideoInfo *i)
 * \note On failure, raise a Python exception and return `NULL`.
 */
#define pgVidInfo_New \
    (*(PyObject * (*)(pg_VideoInfo *)) PYGAMEAPI_GET_SLOT(display, 1))

#define import_pygame_display() IMPORT_PYGAME_MODULE(display)
#endif /* ~PYGAMEAPI_DISPLAY_INTERNAL */

/*
 * SURFACE module
 */
struct pgSubSurface_Data;
struct SDL_Surface;

/**
 * \brief A pygame object that wraps an SDL_Surface. A `pygame.Surface`
 * instance.
 */
typedef struct {
    PyObject_HEAD struct SDL_Surface *surf;
    /**
     * \brief If true, the surface will be freed when the python object is
     * destroyed.
     */
    int owner;
    /**
     * \brief The subsurface data for this surface (if a subsurface).
     */
    struct pgSubSurface_Data *subsurface;
    /**
     * \brief A list of weak references to this surface.
     */
    PyObject *weakreflist;
    /**
     * \brief A list of locks for this surface.
     */
    PyObject *locklist;
    /**
     * \brief Usually a buffer object which the surface gets its data from.
     */
    PyObject *dependency;
} pgSurfaceObject;

/**
 * \brief Convert a `pygame.Surface` instance to an SDL_Surface.
 *
 * \param x A `pygame.Surface` instance.
 * \returns the SDL_Surface field of *x*, a `pygame.Surface` instance.
 *
 * \note SDL_Surface* pgSurface_AsSurface(PyObject *x)
 */
#define pgSurface_AsSurface(x) (((pgSurfaceObject *)x)->surf)

#ifndef PYGAMEAPI_SURFACE_INTERNAL
/**
 * \brief The `pygame.Surface` object Python type.
 */
#define pgSurface_Type (*(PyTypeObject *)PYGAMEAPI_GET_SLOT(surface, 0))

/**
 * \brief Check if *x* is a `pygame.Surface` instance.
 *
 * \param x The object to check.
 * \returns true if *x* is a `pygame.Surface` instance
 *
 * \note Will return false if *x* is a subclass of `pygame.Surface`.
 * \note This macro does not check that *x* is not ``NULL``.
 * \note int pgSurface_Check(PyObject *x)
 */
#define pgSurface_Check(x) \
    (PyObject_IsInstance((x), (PyObject *)&pgSurface_Type))

/**
 * \brief Create a new `pygame.Surface` instance.
 *
 * \param s The SDL surface to wrap in a python object.
 * \param owner If true, the surface will be freed when the python object is
 * destroyed. \returns A new new pygame surface instance for SDL surface *s*.
 * Returns *NULL* on error.
 *
 * \note pgSurfaceObject* pgSurface_New2(SDL_Surface *s, int owner)
 */
#define pgSurface_New2                            \
    (*(pgSurfaceObject * (*)(SDL_Surface *, int)) \
         PYGAMEAPI_GET_SLOT(surface, 1))

/**
 * \brief Sets the SDL surface for a `pygame.Surface` instance.
 *
 * \param self The `pygame.Surface` instance to set the surface for.
 * \param s The SDL surface to set.
 * \param owner If true, the surface will be freed when the python object is
 * destroyed. \returns 0 on success, -1 on failure.
 *
 * \note int pgSurface_SetSurface(pgSurfaceObject *self, SDL_Surface *s, int
 * owner)
 */
#define pgSurface_SetSurface                                              \
    (*(int (*)(pgSurfaceObject *, SDL_Surface *, int))PYGAMEAPI_GET_SLOT( \
        surface, 3))

/**
 * \brief Blit one surface onto another.
 *
 * \param dstobj The destination surface.
 * \param srcobj The source surface.
 * \param dstrect The destination rectangle.
 * \param srcrect The source rectangle.
 * \param the_args The blit flags.
 * \return 0 for success, -1 or -2 for error.
 *
 * \note Is accessible through the C api.
 * \note int pgSurface_Blit(PyObject *dstobj, PyObject *srcobj, SDL_Rect
 * *dstrect, SDL_Rect *srcrect, int the_args)
 */
#define pgSurface_Blit                                                       \
    (*(int (*)(pgSurfaceObject *, pgSurfaceObject *, SDL_Rect *, SDL_Rect *, \
               int))PYGAMEAPI_GET_SLOT(surface, 2))

#define import_pygame_surface()         \
    do {                                \
        IMPORT_PYGAME_MODULE(surface);  \
        if (PyErr_Occurred() != NULL)   \
            break;                      \
        IMPORT_PYGAME_MODULE(surflock); \
    } while (0)

#define pgSurface_New(surface) pgSurface_New2((surface), 1)
#define pgSurface_NewNoOwn(surface) pgSurface_New2((surface), 0)

#endif /* ~PYGAMEAPI_SURFACE_INTERNAL */

/*
 * SURFLOCK module
 * auto imported/initialized by surface
 */
#ifndef PYGAMEAPI_SURFLOCK_INTERNAL
#define pgLifetimeLock_Type (*(PyTypeObject *)PYGAMEAPI_GET_SLOT(surflock, 0))

#define pgLifetimeLock_Check(x) ((x)->ob_type == &pgLifetimeLock_Type)

#define pgSurface_Prep(x) \
    if ((x)->subsurface)  \
    (*(*(void (*)(pgSurfaceObject *))PYGAMEAPI_GET_SLOT(surflock, 1)))(x)

#define pgSurface_Unprep(x) \
    if ((x)->subsurface)    \
    (*(*(void (*)(pgSurfaceObject *))PYGAMEAPI_GET_SLOT(surflock, 2)))(x)

#define pgSurface_Lock \
    (*(int (*)(pgSurfaceObject *))PYGAMEAPI_GET_SLOT(surflock, 3))

#define pgSurface_Unlock \
    (*(int (*)(pgSurfaceObject *))PYGAMEAPI_GET_SLOT(surflock, 4))

#define pgSurface_LockBy \
    (*(int (*)(pgSurfaceObject *, PyObject *))PYGAMEAPI_GET_SLOT(surflock, 5))

#define pgSurface_UnlockBy \
    (*(int (*)(pgSurfaceObject *, PyObject *))PYGAMEAPI_GET_SLOT(surflock, 6))

#define pgSurface_LockLifetime \
    (*(PyObject * (*)(PyObject *, PyObject *)) PYGAMEAPI_GET_SLOT(surflock, 7))
#endif

/*
 * EVENT module
 */
typedef struct pgEventObject pgEventObject;

#ifndef PYGAMEAPI_EVENT_INTERNAL
#define pgEvent_Type (*(PyTypeObject *)PYGAMEAPI_GET_SLOT(event, 0))

#define pgEvent_Check(x) ((x)->ob_type == &pgEvent_Type)

#define pgEvent_New \
    (*(PyObject * (*)(SDL_Event *)) PYGAMEAPI_GET_SLOT(event, 1))

#define pgEvent_New2 \
    (*(PyObject * (*)(int, PyObject *)) PYGAMEAPI_GET_SLOT(event, 2))

#define pgEvent_FillUserEvent \
    (*(int (*)(pgEventObject *, SDL_Event *))PYGAMEAPI_GET_SLOT(event, 3))

#define pg_EnableKeyRepeat (*(int (*)(int, int))PYGAMEAPI_GET_SLOT(event, 4))

#define pg_GetKeyRepeat (*(void (*)(int *, int *))PYGAMEAPI_GET_SLOT(event, 5))

#define import_pygame_event() IMPORT_PYGAME_MODULE(event)
#endif

/*
 * RWOBJECT module
 * the rwobject are only needed for C side work, not accessible from python.
 */
#ifndef PYGAMEAPI_RWOBJECT_INTERNAL
#define pgRWops_FromObject \
    (*(SDL_RWops * (*)(PyObject *, char **)) PYGAMEAPI_GET_SLOT(rwobject, 0))

#define pgRWops_IsFileObject \
    (*(int (*)(SDL_RWops *))PYGAMEAPI_GET_SLOT(rwobject, 1))

#define pg_EncodeFilePath \
    (*(PyObject * (*)(PyObject *, PyObject *)) PYGAMEAPI_GET_SLOT(rwobject, 2))

#define pg_EncodeString                                                    \
    (*(PyObject * (*)(PyObject *, const char *, const char *, PyObject *)) \
         PYGAMEAPI_GET_SLOT(rwobject, 3))

#define pgRWops_FromFileObject \
    (*(SDL_RWops * (*)(PyObject *)) PYGAMEAPI_GET_SLOT(rwobject, 4))

#define pgRWops_ReleaseObject \
    (*(int (*)(SDL_RWops *))PYGAMEAPI_GET_SLOT(rwobject, 5))

#define import_pygame_rwobject() IMPORT_PYGAME_MODULE(rwobject)

#endif

/*
 * PixelArray module
 */
#ifndef PYGAMEAPI_PIXELARRAY_INTERNAL
#define PyPixelArray_Type ((PyTypeObject *)PYGAMEAPI_GET_SLOT(pixelarray, 0))

#define PyPixelArray_Check(x) ((x)->ob_type == &PyPixelArray_Type)
#define PyPixelArray_New (*(PyObject * (*)) PYGAMEAPI_GET_SLOT(pixelarray, 1))

#define import_pygame_pixelarray() IMPORT_PYGAME_MODULE(pixelarray)
#endif /* PYGAMEAPI_PIXELARRAY_INTERNAL */

/*
 * Color module
 */
typedef struct pgColorObject pgColorObject;

#ifndef PYGAMEAPI_COLOR_INTERNAL
#define pgColor_Type (*(PyObject *)PYGAMEAPI_GET_SLOT(color, 0))

#define pgColor_Check(x) ((x)->ob_type == &pgColor_Type)
#define pgColor_New (*(PyObject * (*)(Uint8 *)) PYGAMEAPI_GET_SLOT(color, 1))

#define pgColor_NewLength \
    (*(PyObject * (*)(Uint8 *, Uint8)) PYGAMEAPI_GET_SLOT(color, 3))

#define pg_RGBAFromColorObj \
    (*(int (*)(PyObject *, Uint8 *))PYGAMEAPI_GET_SLOT(color, 2))

#define pg_RGBAFromFuzzyColorObj \
    (*(int (*)(PyObject *, Uint8 *))PYGAMEAPI_GET_SLOT(color, 4))

#define pgColor_AsArray(x) (((pgColorObject *)x)->data)
#define pgColor_NumComponents(x) (((pgColorObject *)x)->len)

#define import_pygame_color() IMPORT_PYGAME_MODULE(color)
#endif /* PYGAMEAPI_COLOR_INTERNAL */

/*
 * Math module
 */
#ifndef PYGAMEAPI_MATH_INTERNAL
#define pgVector2_Check(x) \
    ((x)->ob_type == (PyTypeObject *)PYGAMEAPI_GET_SLOT(math, 0))

#define pgVector3_Check(x) \
    ((x)->ob_type == (PyTypeObject *)PYGAMEAPI_GET_SLOT(math, 1))
/*
#define pgVector2_New                                             \
    (*(PyObject*(*))  \
        PYGAMEAPI_GET_SLOT(PyGAME_C_API, 1))
*/
#define import_pygame_math() IMPORT_PYGAME_MODULE(math)
#endif /* PYGAMEAPI_MATH_INTERNAL */

#define IMPORT_PYGAME_MODULE _IMPORT_PYGAME_MODULE

/*
 * base pygame API slots
 * disable slots with NO_PYGAME_C_API
 */
#ifdef PYGAME_H
PYGAMEAPI_DEFINE_SLOTS(base);
PYGAMEAPI_DEFINE_SLOTS(rect);
PYGAMEAPI_DEFINE_SLOTS(cdrom);
PYGAMEAPI_DEFINE_SLOTS(joystick);
PYGAMEAPI_DEFINE_SLOTS(display);
PYGAMEAPI_DEFINE_SLOTS(surface);
PYGAMEAPI_DEFINE_SLOTS(surflock);
PYGAMEAPI_DEFINE_SLOTS(event);
PYGAMEAPI_DEFINE_SLOTS(rwobject);
PYGAMEAPI_DEFINE_SLOTS(pixelarray);
PYGAMEAPI_DEFINE_SLOTS(color);
PYGAMEAPI_DEFINE_SLOTS(math);
#else  /* ~PYGAME_H */
PYGAMEAPI_EXTERN_SLOTS(base);
PYGAMEAPI_EXTERN_SLOTS(rect);
PYGAMEAPI_EXTERN_SLOTS(cdrom);
PYGAMEAPI_EXTERN_SLOTS(joystick);
PYGAMEAPI_EXTERN_SLOTS(display);
PYGAMEAPI_EXTERN_SLOTS(surface);
PYGAMEAPI_EXTERN_SLOTS(surflock);
PYGAMEAPI_EXTERN_SLOTS(event);
PYGAMEAPI_EXTERN_SLOTS(rwobject);
PYGAMEAPI_EXTERN_SLOTS(pixelarray);
PYGAMEAPI_EXTERN_SLOTS(color);
PYGAMEAPI_EXTERN_SLOTS(math);
#endif /* ~PYGAME_H */

#endif /* PYGAME_H */

/*  Use the end of this file for other cross module inline utility
 *  functions There seems to be no good reason to stick to macro only
 *  functions in Python 3.
 */

static PG_INLINE PyObject *
pg_tuple_couple_from_values_int(int val1, int val2)
{
    /* This function turns two input integers into a python tuple object.
     * Currently, 5th November 2022, this is faster than using Py_BuildValue
     * to do the same thing.
     */
    PyObject *tup = PyTuple_New(2);
    if (!tup) {
        return NULL;
    }

    PyObject *tmp = PyLong_FromLong(val1);
    if (!tmp) {
        Py_DECREF(tup);
        return NULL;
    }
    PyTuple_SET_ITEM(tup, 0, tmp);

    tmp = PyLong_FromLong(val2);
    if (!tmp) {
        Py_DECREF(tup);
        return NULL;
    }
    PyTuple_SET_ITEM(tup, 1, tmp);

    return tup;
}

static PG_INLINE PyObject *
pg_tuple_triple_from_values_int(int val1, int val2, int val3)
{
    /* This function turns three input integers into a python tuple object.
     * Currently, 5th November 2022, this is faster than using Py_BuildValue
     * to do the same thing.
     */
    PyObject *tup = PyTuple_New(3);
    if (!tup) {
        return NULL;
    }

    PyObject *tmp = PyLong_FromLong(val1);
    if (!tmp) {
        Py_DECREF(tup);
        return NULL;
    }
    PyTuple_SET_ITEM(tup, 0, tmp);

    tmp = PyLong_FromLong(val2);
    if (!tmp) {
        Py_DECREF(tup);
        return NULL;
    }
    PyTuple_SET_ITEM(tup, 1, tmp);

    tmp = PyLong_FromLong(val3);
    if (!tmp) {
        Py_DECREF(tup);
        return NULL;
    }
    PyTuple_SET_ITEM(tup, 2, tmp);

    return tup;
}
