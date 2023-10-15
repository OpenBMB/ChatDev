#ifndef PGFONT_INTERNAL_H
#define PGFONT_INTERNAL_H

#include <SDL_ttf.h>

/* test font initialization */
#define FONT_INIT_CHECK()           \
    if (!(*(int *)PyFONT_C_API[2])) \
    return RAISE(pgExc_SDLError, "font system not initialized")

#include "include/pygame_font.h"

#define PYGAMEAPI_FONT_NUMSLOTS 3

#endif /* ~PGFONT_INTERNAL_H */
