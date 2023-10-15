#ifndef MIXER_INTERNAL_H
#define MIXER_INTERNAL_H

#include <SDL_mixer.h>

/* test mixer initializations */
#define MIXER_INIT_CHECK()            \
    if (!SDL_WasInit(SDL_INIT_AUDIO)) \
    return RAISE(pgExc_SDLError, "mixer not initialized")

#define PYGAMEAPI_MIXER_NUMSLOTS 5
#include "include/pygame_mixer.h"

#endif /* ~MIXER_INTERNAL_H */
