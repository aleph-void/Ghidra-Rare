/* Small C program used to sanity-check ELF import, analysis and decompilation of C7x code. */
#include <string.h>
#include <c7x.h>

typedef struct { int id; short kind; long total; } rec_t;

long sum_array(const long *p, long n)
{
    long s = 0;
    long i;
    for (i = 0; i < n; i++)
        s += p[i];
    return s;
}

int clamp(int v, int lo, int hi)
{
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

unsigned int bitfield(unsigned int x)
{
    return ((x >> 3) & 0x1f) | (x << 7);
}

int classify(int c)
{
    switch (c) {
    case 0: return 10;
    case 1: return 21;
    case 2: return 37;
    case 3: return 41;
    case 4: return 59;
    case 5: return 66;
    default: return -1;
    }
}

void rec_update(rec_t *r, int id, short kind)
{
    r->id = id;
    r->kind = kind;
    r->total += (long)id * kind;
}

long big_const(long x)
{
    return x * 0x123456789abcLL + 0x7fff0000;
}

static int helper(int a, int b) { return a * 3 - b; }

int caller(int x)
{
    int (*volatile fp)(int, int) = helper;
    return helper(x, 2) + fp(x, 5);
}

volatile int sink;
char buf[64];

/* ---------------------------------------------------------------- vectors (C7x intrinsics) */
void vec_add(const int *a, const int *b, int *c, int n)
{
    int i;
    for (i = 0; i + 8 <= n; i += 8) {
        __int8 va = *(const __int8 *)(a + i);
        __int8 vb = *(const __int8 *)(b + i);
        *(__int8 *)(c + i) = va + vb;
    }
    for (; i < n; i++)
        c[i] = a[i] + b[i];
}

int vec_dot(const short *a, const short *b, int n)
{
    __int8 acc = (__int8)0;
    int i, s = 0;
    for (i = 0; i + 8 <= n; i += 8) {
        __int8 va = __convert_int8(*(const __short8 *)(a + i));
        __int8 vb = __convert_int8(*(const __short8 *)(b + i));
        acc += va * vb;
    }
    for (i = 0; i < 8; i++)
        s += acc.s[i];
    return s;
}

void vec_scale_clamp(float *x, int n, float k, float lo, float hi)
{
    int i;
    for (i = 0; i < n; i++) {
        float v = x[i] * k;
        x[i] = v < lo ? lo : (v > hi ? hi : v);
    }
}

/* ---------------------------------------------------------------- data structures */
typedef struct node {
    struct node *next;
    int key;
    int value;
} node_t;

static node_t pool[32];
static int pool_used;

node_t *list_push(node_t *head, int key, int value)
{
    node_t *n;
    if (pool_used >= 32) return head;
    n = &pool[pool_used++];
    n->key = key;
    n->value = value;
    n->next = head;
    return n;
}

int list_find(const node_t *head, int key)
{
    for (; head; head = head->next)
        if (head->key == key)
            return head->value;
    return -1;
}

unsigned int crc32(const unsigned char *p, int len)
{
    unsigned int crc = 0xffffffffu;
    int i, j;
    for (i = 0; i < len; i++) {
        crc ^= p[i];
        for (j = 0; j < 8; j++)
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

unsigned int hash_str(const char *s)
{
    unsigned int h = 5381;
    while (*s)
        h = h * 33 + (unsigned char)*s++;
    return h;
}

void bubble_sort(int *a, int n)
{
    int i, j, t;
    for (i = 0; i < n - 1; i++)
        for (j = 0; j < n - 1 - i; j++)
            if (a[j] > a[j + 1]) {
                t = a[j]; a[j] = a[j + 1]; a[j + 1] = t;
            }
}

void matmul4(const int m[4][4], const int v[4], int out[4])
{
    int i, j;
    for (i = 0; i < 4; i++) {
        long s = 0;
        for (j = 0; j < 4; j++)
            s += (long)m[i][j] * v[j];
        out[i] = (int)(s >> 2);
    }
}

long long mul64(long long a, long long b) { return a * b; }
unsigned long udiv(unsigned long a, unsigned long b) { return b ? a / b : 0; }
long sdivmod(long a, long b, long *rem) { *rem = a % b; return a / b; }

/* ---------------------------------------------------------------- state machine with a dispatch table */
typedef enum { ST_IDLE, ST_RUN, ST_WAIT, ST_DONE, ST_COUNT } state_t;
typedef state_t (*handler_t)(int *ctx, int ev);

static state_t on_idle(int *ctx, int ev) { if (ev == 1) { *ctx = 0; return ST_RUN; } return ST_IDLE; }
static state_t on_run(int *ctx, int ev)  { *ctx += ev; return *ctx > 100 ? ST_WAIT : ST_RUN; }
static state_t on_wait(int *ctx, int ev) { return ev == 2 ? ST_DONE : (ev == 3 ? ST_RUN : ST_WAIT); }
static state_t on_done(int *ctx, int ev) { (void)ctx; (void)ev; return ST_DONE; }

static const handler_t handlers[ST_COUNT] = { on_idle, on_run, on_wait, on_done };

state_t run_machine(const int *events, int n)
{
    state_t st = ST_IDLE;
    int ctx = 0, i;
    for (i = 0; i < n && st != ST_DONE; i++)
        st = handlers[st](&ctx, events[i]);
    return st;
}

const char *state_name(state_t s)
{
    switch (s) {
    case ST_IDLE: return "idle";
    case ST_RUN:  return "run";
    case ST_WAIT: return "wait";
    case ST_DONE: return "done";
    default:      return "?";
    }
}

int parse_int(const char *s)
{
    int neg = 0, v = 0;
    while (*s == ' ' || *s == '\t') s++;
    if (*s == '-') { neg = 1; s++; } else if (*s == '+') s++;
    while (*s >= '0' && *s <= '9') v = v * 10 + (*s++ - '0');
    return neg ? -v : v;
}

int bits_popcount(unsigned long x)
{
    int c = 0;
    while (x) { x &= x - 1; c++; }
    return c;
}

volatile int sink2;

int extra_main(void)
{
    static int a[16], b[16], c[16];
    static short sa[16], sb[16];
    static float f[8] = {1.0f, -2.5f, 3.0f, 4.0f, 9.0f, -7.0f, 0.5f, 2.0f};
    static const int m[4][4] = {{1, 2, 3, 4}, {5, 6, 7, 8}, {9, 10, 11, 12}, {13, 14, 15, 16}};
    static const int ev[6] = {1, 50, 60, 2, 0, 0};
    int out[4], i;
    long rem;
    node_t *head = 0;
    for (i = 0; i < 16; i++) { a[i] = i; b[i] = 2 * i; sa[i] = (short)i; sb[i] = (short)(3 - i); }
    vec_add(a, b, c, 16);
    vec_scale_clamp(f, 8, 1.5f, -4.0f, 4.0f);
    for (i = 0; i < 8; i++) head = list_push(head, i, i * i);
    bubble_sort(c, 16);
    matmul4(m, c, out);
    sink2 = vec_dot(sa, sb, 16) + list_find(head, 5) + (int)crc32((const unsigned char *)buf, 3)
          + (int)hash_str(state_name(run_machine(ev, 6))) + out[2] + (int)f[3] + parse_int(" -42")
          + bits_popcount((unsigned long)sink2) + (int)mul64(sink2, 77) + (int)udiv(1000, (unsigned long)sink2 + 1)
          + (int)sdivmod(-1000, 7, &rem) + (int)rem;
    return extra_main();
}

int main(void)
{
    long arr[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    rec_t r = {0, 0, 0};
    rec_update(&r, 5, 3);
    strcpy(buf, "c7x");
    sink = clamp((int)sum_array(arr, 8), 0, 30) + (int)bitfield(sink) + classify(sink) + caller(4)
         + (int)big_const(sink) + (int)strlen(buf) + (int)r.total;
    return extra_main();
}
