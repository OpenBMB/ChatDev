/* platform/compiler adjustments */
#ifndef PG_PLATFORM_H
#define PG_PLATFORM_H

#if defined(HAVE_SNPRINTF) /* defined in python.h (pyerrors.h) and SDL.h \
                              (SDL_config.h) */
#undef HAVE_SNPRINTF       /* remove GCC redefine warning */
#endif                     /* HAVE_SNPRINTF */

#ifndef PG_INLINE
#if defined(__clang__)
#define PG_INLINE __inline__ __attribute__((__unused__))
#elif defined(__GNUC__)
#define PG_INLINE __inline__
#elif defined(_MSC_VER)
#define PG_INLINE __inline
#elif defined(__STDC_VERSION__) && __STDC_VERSION__ >= 199901L
#define PG_INLINE inline
#else
#define PG_INLINE
#endif
#endif /* ~PG_INLINE */

// Worth trying this on MSVC/win32 builds to see if provides any speed up
#ifndef PG_FORCEINLINE
#if defined(__clang__)
#define PG_FORCEINLINE __inline__ __attribute__((__unused__))
#elif defined(__GNUC__)
#define PG_FORCEINLINE __inline__
#elif defined(_MSC_VER)
#define PG_FORCEINLINE __forceinline
#elif defined(__STDC_VERSION__) && __STDC_VERSION__ >= 199901L
#define PG_FORCEINLINE inline
#else
#define PG_FORCEINLINE
#endif
#endif /* ~PG_FORCEINLINE */

/* This is unconditionally defined in Python.h */
#if defined(_POSIX_C_SOURCE)
#undef _POSIX_C_SOURCE
#endif

#if defined(HAVE_SNPRINTF)
#undef HAVE_SNPRINTF
#endif

/* SDL needs WIN32 */
#if !defined(WIN32) &&                                           \
    (defined(MS_WIN32) || defined(_WIN32) || defined(__WIN32) || \
     defined(__WIN32__) || defined(_WINDOWS))
#define WIN32
#endif

/* Commenting out SSE4_2 stuff because it does not do runtime detection.
#ifndef PG_TARGET_SSE4_2
#if defined(__clang__) || (defined(__GNUC__) && ((__GNUC__ == 4 &&
__GNUC_MINOR__ >= 9) || __GNUC__ >= 5 ))
//The old gcc 4.8 on centos used by manylinux1 does not seem to get sse4.2
intrinsics #define PG_FUNCTION_TARGET_SSE4_2 __attribute__((target("sse4.2")))
// No else; we define the fallback later
#endif
#endif
*/
/* ~PG_TARGET_SSE4_2 */

/*
#ifdef PG_FUNCTION_TARGET_SSE4_2
#if !defined(__SSE4_2__) && !defined(PG_COMPILE_SSE4_2)
#if defined(__x86_64__) || defined(__i386__)
#define PG_COMPILE_SSE4_2 1
#endif
#endif
#endif
*/
/* ~PG_TARGET_SSE4_2 */

/* Fallback definition of target attribute */
#ifndef PG_FUNCTION_TARGET_SSE4_2
#define PG_FUNCTION_TARGET_SSE4_2
#endif

#ifndef PG_COMPILE_SSE4_2
#define PG_COMPILE_SSE4_2 0
#endif

#endif /* ~PG_PLATFORM_H */
