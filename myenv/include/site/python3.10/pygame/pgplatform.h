/* platform/compiler adjustments (internal) */
#ifndef PG_PLATFORM_INTERNAL_H
#define PG_PLATFORM_INTERNAL_H

#include "include/pgplatform.h"

#ifndef MIN
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#endif
#ifndef MAX
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#endif
#ifndef ABS
#define ABS(a) (((a) < 0) ? -(a) : (a))
#endif

/* warnings */
#define PG_STRINGIZE_HELPER(x) #x
#define PG_STRINGIZE(x) PG_STRINGIZE_HELPER(x)
#define PG_WARN(desc) \
    message(__FILE__ "(" PG_STRINGIZE(__LINE__) "): WARNING: " #desc)

#endif /* ~PG_PLATFORM_INTERNAL_H */
