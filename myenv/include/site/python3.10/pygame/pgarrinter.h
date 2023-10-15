/* array structure interface version 3 declarations */

#if !defined(PG_ARRAYINTER_HEADER)
#define PG_ARRAYINTER_HEADER

static const int PAI_CONTIGUOUS = 0x01;
static const int PAI_FORTRAN = 0x02;
static const int PAI_ALIGNED = 0x100;
static const int PAI_NOTSWAPPED = 0x200;
static const int PAI_WRITEABLE = 0x400;
static const int PAI_ARR_HAS_DESCR = 0x800;

typedef struct {
    int two;              /* contains the integer 2 -- simple sanity check */
    int nd;               /* number of dimensions */
    char typekind;        /* kind in array -- character code of typestr */
    int itemsize;         /* size of each element */
    int flags;            /* flags indicating how the data should be */
                          /* interpreted */
    Py_intptr_t *shape;   /* A length-nd array of shape information */
    Py_intptr_t *strides; /* A length-nd array of stride information */
    void *data;           /* A pointer to the first element of the array */
    PyObject *descr;      /* NULL or a data-description */
} PyArrayInterface;

#endif
