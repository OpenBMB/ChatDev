#define NO_PYGAME_C_API
#include "_surface.h"

/* The structure passed to the low level blit functions */
typedef struct {
    int width;
    int height;
    Uint8 *s_pixels;
    int s_pxskip;
    int s_skip;
    Uint8 *d_pixels;
    int d_pxskip;
    int d_skip;
    SDL_PixelFormat *src;
    SDL_PixelFormat *dst;
    Uint8 src_blanket_alpha;
    int src_has_colorkey;
    Uint32 src_colorkey;
    SDL_BlendMode src_blend;
    SDL_BlendMode dst_blend;
} SDL_BlitInfo;
