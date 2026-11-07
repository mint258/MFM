/* Independent CSR posting prototype: exact integer intersections, NOT adopted. */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <stddef.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
#ifdef Py_GIL_DISABLED
#error "CPython GIL required for this prototype LRU/reservation state"
#endif

#define WIDTH 256
#define WORDS 32
#define POPS 2049
#define ORDERS 64
#define RESERVE (16ULL << 20)
#define CAPSULE "exact_nn_inverted_cpp_v1.private_reference"
_Static_assert(CHAR_BIT == 8 && sizeof(uint64_t) == 8, "8-bit bytes/64-bit words required");
_Static_assert(UINT16_MAX >= 2048 && sizeof(uint32_t) == 4, "Exact uint16 intersections/uint32 postings required");

typedef unsigned (*Popcount)(uint64_t);
static unsigned portable_popcount(uint64_t x) {
    x -= (x >> 1) & UINT64_C(0x5555555555555555);
    x = (x & UINT64_C(0x3333333333333333)) + ((x >> 2) & UINT64_C(0x3333333333333333));
    x = (x + (x >> 4)) & UINT64_C(0x0f0f0f0f0f0f0f0f);
    return (unsigned)((x * UINT64_C(0x0101010101010101)) >> 56);
}
#if defined(__GNUC__) && (defined(__x86_64__) || defined(__i386__))
#define X86_DISPATCH 1
__attribute__((target("popcnt")))
static unsigned hardware_popcount(uint64_t x) { return (unsigned)__builtin_popcountll(x); }
#endif
static Popcount popcount = portable_popcount;
static const char *popcount_name = "portable_uint64_swar";

typedef struct {
    uint64_t *words, *ordinals;
    size_t n, capacity;
} Group;
typedef struct { uint16_t numerator, denominator, pop; } Bound;
typedef struct {
    Bound values[POPS];
    size_t n;
    unsigned qbits;
    uint64_t age;
    int used;
} Order;
typedef struct {
    Group groups[POPS];
    Order orders[ORDERS];
    uint64_t n, cap, tick;
    size_t buffer_bytes;
    size_t bit_counts[2048], offsets[2049];
    uint32_t *postings;
    size_t posting_count;
    int sealed;
} Cache;
/* Reservation is module-wide, GIL protected, including lazy malloc pages. */
static size_t inflight_workspace_bytes = 0;

static int rss_bytes(uint64_t *result) {
    unsigned long long pages, resident;
    FILE *file = fopen("/proc/self/statm", "r");
    long page = sysconf(_SC_PAGESIZE);
    if (!file || page <= 0) {
        if (file) fclose(file);
        PyErr_SetString(PyExc_RuntimeError, "LINUX_ACTUAL_RSS_REQUIRED"); return -1;
    }
    int read = fscanf(file, "%llu %llu", &pages, &resident); fclose(file);
    if (read != 2 || resident > UINT64_MAX / (uint64_t)page) {
        PyErr_SetString(PyExc_RuntimeError, "INVALID_ACTUAL_RSS"); return -1;
    }
    *result = resident * (uint64_t)page; return 0;
}
static int headroom(uint64_t cap, size_t extra) {
    uint64_t rss;
    if (rss_bytes(&rss) < 0) return -1;
    /* Include concurrent reserved query mallocs, even if their pages are lazy.
       Resident reserved pages can be counted twice: deliberately conservative. */
    if ((uint64_t)extra > UINT64_MAX - (uint64_t)inflight_workspace_bytes) {
        PyErr_SetString(PyExc_OverflowError, "RSS_RESERVATION_OVERFLOW"); return -1;
    }
    uint64_t requested = (uint64_t)extra + (uint64_t)inflight_workspace_bytes;
    if (rss > cap || RESERVE > cap - rss || requested > cap - rss - RESERVE) {
        PyErr_SetString(PyExc_RuntimeError, "PROTOTYPE_ACTUAL_RSS_PLUS_PEAK_BUFFER_AND_WORKSPACE_EXCEEDS_CAP"); return -1;
    }
    return 0;
}
static Cache *cache_arg(PyObject *capsule) { return PyCapsule_GetPointer(capsule, CAPSULE); }
static void destroy(PyObject *capsule) {
    Cache *c = cache_arg(capsule);
    if (!c) { PyErr_Clear(); return; }
    for (unsigned p = 0; p < POPS; ++p) { free(c->groups[p].words); free(c->groups[p].ordinals); }
    free(c->postings); free(c);
}
static int raw_words(PyObject *raw, uint64_t out[WORDS], unsigned *bits) {
    if (!PyBytes_Check(raw) || PyBytes_GET_SIZE(raw) != WIDTH) {
        PyErr_SetString(PyExc_ValueError, "EXACT_2048BIT_IMMUTABLE_BYTES_REQUIRED"); return -1;
    }
    const unsigned char *data = (const unsigned char *)PyBytes_AS_STRING(raw);
    *bits = 0;
    for (unsigned i = 0; i < WORDS; ++i) {
        memcpy(out + i, data + i * 8, 8); /* No unaligned/aliasing-unsafe casts. */
#if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
        out[i] = __builtin_bswap64(out[i]); /* Canonical raw byte/bit numbering. */
#endif
        *bits += popcount(out[i]);
    }
    return 0;
}
static PyObject *create(PyObject *self, PyObject *args) {
    (void)self;
    PyObject *cap_value;
    if (!PyArg_ParseTuple(args, "O", &cap_value)) return NULL;
    if (!PyLong_CheckExact(cap_value)) { PyErr_SetString(PyExc_ValueError, "INTEGER_WORKER_CAP_REQUIRED"); return NULL; }
    unsigned long long cap = PyLong_AsUnsignedLongLong(cap_value);
    if (PyErr_Occurred()) return NULL;
    if (cap == 0) { PyErr_SetString(PyExc_ValueError, "POSITIVE_WORKER_CAP_REQUIRED"); return NULL; }
    if (headroom(cap, sizeof(Cache)) < 0) return NULL;
    Cache *c = calloc(1, sizeof(Cache));
    if (!c) return PyErr_NoMemory();
    c->cap = cap;
    PyObject *capsule = PyCapsule_New(c, CAPSULE, destroy);
    if (!capsule) free(c);
    return capsule;
}
static PyObject *append(PyObject *self, PyObject *args) {
    (void)self;
    PyObject *capsule, *raw;
    if (!PyArg_ParseTuple(args, "OO", &capsule, &raw)) return NULL;
    Cache *c = cache_arg(capsule); if (!c) return NULL;
    if (c->sealed) { PyErr_SetString(PyExc_ValueError, "SEALED_PRIVATE_REFERENCE"); return NULL; }
    if (c->n >= (uint64_t)UINT32_MAX || c->n >= (uint64_t)PY_SSIZE_T_MAX) { PyErr_SetString(PyExc_OverflowError, "REFERENCE_TOO_LARGE"); return NULL; }
    uint64_t words[WORDS]; unsigned bits;
    if (raw_words(raw, words, &bits) < 0) return NULL;
    Group *g = c->groups + bits;
    if (g->n == g->capacity) {
        size_t capacity = g->capacity ? g->capacity * 2 : 8;
        if (capacity < g->capacity || capacity > SIZE_MAX / (WIDTH + sizeof(uint64_t))) {
            PyErr_SetString(PyExc_OverflowError, "PRIVATE_REFERENCE_ALLOCATION_OVERFLOW"); return NULL;
        }
        size_t word_bytes = capacity * WIDTH, ordinal_bytes = capacity * sizeof(uint64_t);
        size_t retained = c->buffer_bytes - g->capacity * (WIDTH + sizeof(uint64_t));
        if (word_bytes + ordinal_bytes > SIZE_MAX - retained) { PyErr_SetString(PyExc_OverflowError, "TOTAL_PRIVATE_BUFFER_OVERFLOW"); return NULL; }
        if (headroom(c->cap, word_bytes + ordinal_bytes) < 0) return NULL;
        uint64_t *new_words = malloc(word_bytes), *new_ordinals = malloc(ordinal_bytes);
        if (!new_words || !new_ordinals) { free(new_words); free(new_ordinals); return PyErr_NoMemory(); }
        if (g->n) {
            memcpy(new_words, g->words, g->n * WIDTH);
            memcpy(new_ordinals, g->ordinals, g->n * sizeof(uint64_t));
        }
        free(g->words); free(g->ordinals);
        c->buffer_bytes -= g->capacity * (WIDTH + sizeof(uint64_t));
        g->words = new_words; g->ordinals = new_ordinals; g->capacity = capacity;
        c->buffer_bytes += word_bytes + ordinal_bytes;
    }
    for (unsigned w = 0; w < WORDS; ++w) {
        uint64_t bits = words[w];
        while (bits) {
            unsigned bit = w * 64 + (unsigned)__builtin_ctzll(bits);
            ++c->bit_counts[bit]; bits &= bits - 1;
        }
    }
    memcpy(g->words + g->n * WORDS, words, WIDTH);
    g->ordinals[g->n] = c->n; ++g->n; ++c->n;
    Py_RETURN_NONE;
}
static PyObject *seal(PyObject *self, PyObject *args) {
    (void)self;
    PyObject *capsule; if (!PyArg_ParseTuple(args, "O", &capsule)) return NULL;
    Cache *c = cache_arg(capsule); if (!c) return NULL;
    if (!c->n) { PyErr_SetString(PyExc_ValueError, "EMPTY_REFERENCE_FORBIDDEN"); return NULL; }
    if (c->sealed) Py_RETURN_NONE;
    c->offsets[0] = 0;
    for (unsigned bit = 0; bit < 2048; ++bit) {
        if (c->bit_counts[bit] > SIZE_MAX - c->offsets[bit]) {
            PyErr_SetString(PyExc_OverflowError, "CSR_POSTING_COUNT_OVERFLOW"); return NULL;
        }
        c->offsets[bit + 1] = c->offsets[bit] + c->bit_counts[bit];
    }
    size_t count = c->offsets[2048];
    if (count > SIZE_MAX / sizeof(uint32_t)) {
        PyErr_SetString(PyExc_OverflowError, "CSR_POSTING_BYTES_OVERFLOW"); return NULL;
    }
    size_t bytes = count * sizeof(uint32_t);
    if (bytes > SIZE_MAX - c->buffer_bytes || headroom(c->cap, bytes) < 0) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_OverflowError, "CSR_TOTAL_BUFFER_OVERFLOW");
        return NULL;
    }
    uint32_t *postings = count ? malloc(bytes) : NULL;
    if (count && !postings) return PyErr_NoMemory();
    size_t cursor[2048]; memcpy(cursor, c->offsets, sizeof(cursor));
    for (unsigned p = 0; p < POPS; ++p) {
        Group *g = c->groups + p;
        for (size_t i = 0; i < g->n; ++i) {
            const uint64_t *words = g->words + i * WORDS;
            for (unsigned w = 0; w < WORDS; ++w) {
                uint64_t bits = words[w];
                while (bits) {
                    unsigned bit = w * 64 + (unsigned)__builtin_ctzll(bits);
                    postings[cursor[bit]++] = (uint32_t)g->ordinals[i];
                    bits &= bits - 1;
                }
            }
        }
    }
    for (unsigned bit = 0; bit < 2048; ++bit) {
        if (cursor[bit] != c->offsets[bit + 1]) {
            free(postings); PyErr_SetString(PyExc_RuntimeError, "INCOMPLETE_CSR_POSTINGS"); return NULL;
        }
    }
    c->postings = postings; c->posting_count = count; c->buffer_bytes += bytes;
    /* CSR is now a private immutable representation. Raw builder copies have
       no query role; free them only AFTER the whole posting allocation succeeds. */
    for (unsigned p = 0; p < POPS; ++p) {
        Group *g = c->groups + p;
        free(g->words); g->words = NULL; c->buffer_bytes -= g->capacity * WIDTH;
    }
    c->sealed = 1; Py_RETURN_NONE;
}
static int compare_bound(const void *left, const void *right) {
    const Bound *a = left, *b = right;
    uint64_t ab = (uint64_t)a->numerator * b->denominator;
    uint64_t ba = (uint64_t)b->numerator * a->denominator;
    if (ab != ba) return ab > ba ? -1 : 1;
    return (a->pop > b->pop) - (a->pop < b->pop);
}
static Order *get_order(Cache *c, unsigned qbits) {
    Order *slot = NULL;
    if (c->tick == UINT64_MAX) { PyErr_SetString(PyExc_OverflowError, "ORDER_LRU_CLOCK_OVERFLOW"); return NULL; }
    for (unsigned i = 0; i < ORDERS; ++i) {
        Order *o = c->orders + i;
        if (o->used && o->qbits == qbits) { o->age = ++c->tick; return o; }
        if (!slot || (!o->used && slot->used) || (o->used && slot->used && o->age < slot->age)) slot = o;
    }
    slot->n = 0; slot->qbits = qbits; slot->used = 1; slot->age = ++c->tick;
    for (unsigned p = 0; p < POPS; ++p) if (c->groups[p].n) {
        unsigned maximum = qbits > p ? qbits : p, minimum = qbits < p ? qbits : p;
        Bound b = {(uint16_t)minimum, (uint16_t)(maximum ? maximum : 1), (uint16_t)p};
        slot->values[slot->n++] = b;
    }
    qsort(slot->values, slot->n, sizeof(Bound), compare_bound);
    return slot;
}
static PyObject *order(PyObject *self, PyObject *args) {
    (void)self;
    PyObject *capsule; unsigned qbits;
    if (!PyArg_ParseTuple(args, "OI", &capsule, &qbits)) return NULL;
    Cache *c = cache_arg(capsule); if (!c) return NULL;
    if (!c->sealed || qbits > 2048) { PyErr_SetString(PyExc_ValueError, "SEALED_REFERENCE_AND_2048BIT_POPCOUNT_REQUIRED"); return NULL; }
    Order *o = get_order(c, qbits); if (!o) return NULL;
    PyObject *result = PyTuple_New((Py_ssize_t)o->n); if (!result) return NULL;
    for (size_t i = 0; i < o->n; ++i) {
        Bound b = o->values[i]; PyObject *row = Py_BuildValue("(III)", (unsigned)b.numerator, (unsigned)b.denominator, (unsigned)b.pop);
        if (!row) { Py_DECREF(result); return NULL; }
        PyTuple_SET_ITEM(result, (Py_ssize_t)i, row);
    }
    return result;
}
static PyObject *nearest_impl(PyObject *args, int profiled) {
    PyObject *capsule, *raw;
    if (!PyArg_ParseTuple(args, "OO", &capsule, &raw)) return NULL;
    Cache *c = cache_arg(capsule); if (!c) return NULL;
    if (!c->sealed) { PyErr_SetString(PyExc_ValueError, "SEALED_PRIVATE_REFERENCE_REQUIRED"); return NULL; }
    uint64_t words[WORDS]; unsigned qbits;
    if (raw_words(raw, words, &qbits) < 0 || headroom(c->cap, 0) < 0) return NULL;
    Order *o = get_order(c, qbits); if (!o) return NULL;
    /* Copy order before releasing the GIL: concurrent calls may update its LRU. */
    Bound bounds[POPS]; size_t order_n = o->n;
    memcpy(bounds, o->values, order_n * sizeof(Bound));
    if (c->n > SIZE_MAX / sizeof(uint16_t)) {
        PyErr_SetString(PyExc_OverflowError, "QUERY_INTERSECTION_BYTES_OVERFLOW"); return NULL;
    }
    size_t workspace = (size_t)c->n * sizeof(uint16_t);
    if (workspace > SIZE_MAX - inflight_workspace_bytes) {
        PyErr_SetString(PyExc_OverflowError, "CONCURRENT_QUERY_WORKSPACE_OVERFLOW"); return NULL;
    }
    if (headroom(c->cap, workspace) < 0) return NULL;
    uint16_t *intersections = malloc(workspace);
    if (!intersections) return PyErr_NoMemory();
    inflight_workspace_bytes += workspace; /* GIL protects reservations. */
    uint16_t searched[POPS]; size_t searched_n = 0;
    uint64_t posting_visits = 0;
    uint64_t best_index = 0, evaluated = 0, pruned = 0;
    unsigned best_num = 0, best_den = 1; int have_best = 0;
    Py_BEGIN_ALLOW_THREADS
    memset(intersections, 0, workspace);
    for (unsigned w = 0; w < WORDS; ++w) {
        uint64_t bits = words[w];
        while (bits) {
            unsigned bit = w * 64 + (unsigned)__builtin_ctzll(bits);
            size_t begin = c->offsets[bit], end = c->offsets[bit + 1];
            posting_visits += (uint64_t)(end - begin);
            for (size_t at = begin; at < end; ++at) ++intersections[c->postings[at]];
            bits &= bits - 1;
        }
    }
    for (size_t gi = 0; gi < order_n; ++gi) {
        Bound b = bounds[gi]; Group *g = c->groups + b.pop;
        if (have_best && (uint64_t)b.numerator * best_den < (uint64_t)best_num * b.denominator) {
            pruned += g->n; continue;
        }
        searched[searched_n++] = b.pop; evaluated += g->n;
        unsigned local_num = 0, local_den = 1; uint64_t local_index = 0; int have_local = 0;
        for (size_t i = 0; i < g->n; ++i) {
            unsigned common = intersections[g->ordinals[i]];
            unsigned union_bits = qbits + b.pop - common;
            unsigned numerator = union_bits ? common : 0, denominator = union_bits ? union_bits : 1;
            /* Local equal scores retain FIRST original ordinal in this group. */
            if (!have_local || (uint64_t)numerator * local_den > (uint64_t)local_num * denominator) {
                have_local = 1; local_num = numerator; local_den = denominator; local_index = g->ordinals[i];
            }
        }
        uint64_t comparison_a = (uint64_t)local_num * best_den;
        uint64_t comparison_b = (uint64_t)best_num * local_den;
        if (!have_best || comparison_a > comparison_b || (comparison_a == comparison_b && local_index < best_index)) {
            have_best = 1; best_num = local_num; best_den = local_den; best_index = local_index;
        }
    }
    free(intersections);
    Py_END_ALLOW_THREADS
    inflight_workspace_bytes -= workspace;
    if (!have_best || evaluated + pruned != c->n) { PyErr_SetString(PyExc_RuntimeError, "INCOMPLETE_FULL_REFERENCE_GROUP_ACCOUNTING"); return NULL; }
    PyObject *groups = PyList_New((Py_ssize_t)searched_n); if (!groups) return NULL;
    for (size_t i = 0; i < searched_n; ++i) {
        PyObject *value = PyLong_FromUnsignedLong(searched[i]);
        if (!value) { Py_DECREF(groups); return NULL; }
        PyList_SET_ITEM(groups, (Py_ssize_t)i, value);
    }
    PyObject *result = Py_BuildValue("{s:K,s:I,s:I,s:K,s:K,s:K,s:N}",
        "reference_ordinal", (unsigned long long)best_index,
        "score_numerator", best_num, "score_denominator", best_den,
        "evaluated_references", (unsigned long long)evaluated,
        "strictly_bound_pruned_references", (unsigned long long)pruned,
        "reference_molecules", (unsigned long long)c->n,
        "searched_popcount_groups", groups);
    if (!result || !profiled) return result;
    PyObject *work = Py_BuildValue("{s:K,s:K,s:K,s:K,s:K,s:K,s:K,s:O}",
        "query_set_bits", (unsigned long long)qbits,
        "posting_lists_visited", (unsigned long long)qbits,
        "posting_entries_visited", (unsigned long long)posting_visits,
        "intersection_counter_increments", (unsigned long long)posting_visits,
        "intersection_counters_zeroed", (unsigned long long)c->n,
        "winner_scan_rows", (unsigned long long)evaluated,
        "group_bounds_checked", (unsigned long long)order_n,
        "logically_pruned_rows_may_have_posting_work", Py_True);
    if (!work) { Py_DECREF(result); return NULL; }
    return Py_BuildValue("(NN)", result, work);
}
static PyObject *nearest(PyObject *self, PyObject *args) {
    (void)self; return nearest_impl(args, 0);
}
static PyObject *nearest_profiled(PyObject *self, PyObject *args) {
    (void)self; return nearest_impl(args, 1);
}
static PyObject *stats(PyObject *self, PyObject *args) {
    (void)self;
    PyObject *capsule; if (!PyArg_ParseTuple(args, "O", &capsule)) return NULL;
    Cache *c = cache_arg(capsule); if (!c) return NULL;
    PyObject *counts = PyDict_New(); if (!counts) return NULL;
    for (unsigned p = 0; p < POPS; ++p) if (c->groups[p].n) {
        PyObject *key = PyLong_FromUnsignedLong(p), *value = PyLong_FromSize_t(c->groups[p].n);
        if (!key || !value || PyDict_SetItem(counts, key, value) < 0) { Py_XDECREF(key); Py_XDECREF(value); Py_DECREF(counts); return NULL; }
        Py_DECREF(key); Py_DECREF(value);
    }
    return Py_BuildValue("{s:K,s:K,s:K,s:i,s:N,s:K,s:K,s:K,s:K,s:K}", "reference_records_loaded", (unsigned long long)c->n,
        "private_buffer_capacity_bytes", (unsigned long long)c->buffer_bytes,
        "workspace_reserve_bytes", (unsigned long long)RESERVE, "sealed", c->sealed, "popcount_groups", counts,
        "posting_entries", (unsigned long long)c->posting_count,
        "posting_buffer_bytes", (unsigned long long)c->posting_count * sizeof(uint32_t),
        "query_workspace_bytes_per_call", (unsigned long long)c->n * sizeof(uint16_t),
        "raw_fingerprint_bytes_retained", c->sealed ? 0ULL : (unsigned long long)c->n * WIDTH,
        "maximum_reference_records_supported", (unsigned long long)UINT32_MAX);
}
static PyObject *build_info(PyObject *self, PyObject *args) {
    (void)self; (void)args;
    return Py_BuildValue("{s:s,s:s,s:s,s:I,s:I,s:s,s:I,s:I}",
        "implementation", "INTEGER_INVERTED_CSR_PRIVATE_COPY_PROTOTYPE_V1",
        "compiled_python", PY_VERSION, "runtime_popcount_backend", popcount_name,
        "width_bytes", (unsigned)WIDTH, "uint64_bytes", (unsigned)sizeof(uint64_t),
        "intersection_backend", "CSR_BIT_POSTINGS_THEN_ORIGINAL_LOGICAL_GROUP_SCAN",
        "intersection_counter_bytes", (unsigned)sizeof(uint16_t),
        "posting_ordinal_bytes", (unsigned)sizeof(uint32_t));
}
static PyMethodDef methods[] = {
    {"create", create, METH_VARARGS, "Create private capped reference builder."},
    {"append", append, METH_VARARGS, "Append immutable2048bit reference preserving ordinal."},
    {"seal", seal, METH_VARARGS, "Seal nonempty reference; no subsequent append."},
    {"nearest", nearest, METH_VARARGS, "Same seven logical exact fields; CSR work is separate."},
    {"nearest_profiled", nearest_profiled, METH_VARARGS, "Exact seven fields plus explicit physical posting-work counters."},
    {"order", order, METH_VARARGS, "Expose exact upper-bound order for parity fixtures."},
    {"stats", stats, METH_VARARGS, "Private allocation/record metadata; not RDKit decode metrics."},
    {"build_info", build_info, METH_NOARGS, "New implementation/runtime CPU metadata."},
    {NULL, NULL, 0, NULL}
};
static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT, "_ecfp4_inverted_kernel_v1", "Independent CPU integer prototype; not production adopted.",
    -1, methods, NULL, NULL, NULL, NULL
};
PyMODINIT_FUNC PyInit__ecfp4_inverted_kernel_v1(void) {
#ifdef X86_DISPATCH
    __builtin_cpu_init();
    if (__builtin_cpu_supports("popcnt")) { popcount = hardware_popcount; popcount_name = "x86_runtime_popcnt"; }
#endif
    return PyModule_Create(&module);
}
