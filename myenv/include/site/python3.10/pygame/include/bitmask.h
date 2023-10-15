/*
    Bitmask 1.7 - A pixel-perfect collision detection library.

    Copyright (C) 2002-2005 Ulf Ekstrom except for the bitcount
    function which is copyright (C) Donald W. Gillies, 1992.

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
#ifndef BITMASK_H
#define BITMASK_H

#ifdef __cplusplus
extern "C" {
#endif

#include <limits.h>
/* Define INLINE for different compilers.  If your compiler does not
   support inlining then there might be a performance hit in
   bitmask_overlap_area().
*/
#ifndef INLINE
#ifdef __GNUC__
#define INLINE inline
#else
#ifdef _MSC_VER
#define INLINE __inline
#else
#define INLINE
#endif
#endif
#endif

#define BITMASK_W unsigned long int
#define BITMASK_W_LEN (sizeof(BITMASK_W) * CHAR_BIT)
#define BITMASK_W_MASK (BITMASK_W_LEN - 1)
#define BITMASK_N(n) ((BITMASK_W)1 << (n))

typedef struct bitmask {
    int w, h;
    BITMASK_W bits[1];
} bitmask_t;

/* Creates a bitmask of width w and height h, where
   w and h must both be greater than or equal to 0.
   The mask is automatically cleared when created.
 */
bitmask_t *
bitmask_create(int w, int h);

/* Frees all the memory allocated by bitmask_create for m. */
void
bitmask_free(bitmask_t *m);

/* Create a copy of the given bitmask. */
bitmask_t *
bitmask_copy(bitmask_t *m);

/* Clears all bits in the mask */
void
bitmask_clear(bitmask_t *m);

/* Sets all bits in the mask */
void
bitmask_fill(bitmask_t *m);

/* Flips all bits in the mask */
void
bitmask_invert(bitmask_t *m);

/* Counts the bits in the mask */
unsigned int
bitmask_count(bitmask_t *m);

/* Returns nonzero if the bit at (x,y) is set.  Coordinates start at
   (0,0) */
static INLINE int
bitmask_getbit(const bitmask_t *m, int x, int y)
{
    return (m->bits[x / BITMASK_W_LEN * m->h + y] &
            BITMASK_N(x & BITMASK_W_MASK)) != 0;
}

/* Sets the bit at (x,y) */
static INLINE void
bitmask_setbit(bitmask_t *m, int x, int y)
{
    m->bits[x / BITMASK_W_LEN * m->h + y] |= BITMASK_N(x & BITMASK_W_MASK);
}

/* Clears the bit at (x,y) */
static INLINE void
bitmask_clearbit(bitmask_t *m, int x, int y)
{
    m->bits[x / BITMASK_W_LEN * m->h + y] &= ~BITMASK_N(x & BITMASK_W_MASK);
}

/* Returns nonzero if the masks overlap with the given offset.
   The overlap tests uses the following offsets (which may be negative):

   +----+----------..
   |A   | yoffset
   |  +-+----------..
   +--|B
   |xoffset
   |  |
   :  :
*/
int
bitmask_overlap(const bitmask_t *a, const bitmask_t *b, int xoffset,
                int yoffset);

/* Like bitmask_overlap(), but will also give a point of intersection.
   x and y are given in the coordinates of mask a, and are untouched
   if there is no overlap. */
int
bitmask_overlap_pos(const bitmask_t *a, const bitmask_t *b, int xoffset,
                    int yoffset, int *x, int *y);

/* Returns the number of overlapping 'pixels' */
int
bitmask_overlap_area(const bitmask_t *a, const bitmask_t *b, int xoffset,
                     int yoffset);

/* Fills a mask with the overlap of two other masks. A bitwise AND. */
void
bitmask_overlap_mask(const bitmask_t *a, const bitmask_t *b, bitmask_t *c,
                     int xoffset, int yoffset);

/* Draws mask b onto mask a (bitwise OR). Can be used to compose large
   (game background?) mask from several submasks, which may speed up
   the testing. */

void
bitmask_draw(bitmask_t *a, const bitmask_t *b, int xoffset, int yoffset);

void
bitmask_erase(bitmask_t *a, const bitmask_t *b, int xoffset, int yoffset);

/* Return a new scaled bitmask, with dimensions w*h. The quality of the
   scaling may not be perfect for all circumstances, but it should
   be reasonable. If either w or h is 0 a clear 1x1 mask is returned. */
bitmask_t *
bitmask_scale(const bitmask_t *m, int w, int h);

/* Convolve b into a, drawing the output into o, shifted by offset.  If offset
 * is 0, then the (x,y) bit will be set if and only if
 * bitmask_overlap(a, b, x - b->w - 1, y - b->h - 1) returns true.
 *
 * Modifies bits o[xoffset ... xoffset + a->w + b->w - 1)
 *                [yoffset ... yoffset + a->h + b->h - 1). */
void
bitmask_convolve(const bitmask_t *a, const bitmask_t *b, bitmask_t *o,
                 int xoffset, int yoffset);

#ifdef __cplusplus
} /* End of extern "C" { */
#endif

#endif
