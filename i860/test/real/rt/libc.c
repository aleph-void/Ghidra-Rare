/* Tiny C library for the i860 test programs (bare metal): just what zlib and Embench call.
 * Written for this module (MIT). */
typedef unsigned long size_t;

void *memcpy(void *d, const void *s, size_t n)
{
	char *dp = d;
	const char *sp = s;
	while (n--)
		*dp++ = *sp++;
	return d;
}

void *memmove(void *d, const void *s, size_t n)
{
	char *dp = d;
	const char *sp = s;
	if (dp < sp) {
		while (n--)
			*dp++ = *sp++;
	} else {
		dp += n;
		sp += n;
		while (n--)
			*--dp = *--sp;
	}
	return d;
}

void *memset(void *d, int c, size_t n)
{
	unsigned char *dp = d;
	while (n--)
		*dp++ = (unsigned char)c;
	return d;
}

int memcmp(const void *a, const void *b, size_t n)
{
	const unsigned char *x = a, *y = b;
	for (; n; n--, x++, y++)
		if (*x != *y)
			return *x - *y;
	return 0;
}

size_t strlen(const char *s)
{
	const char *p = s;
	while (*p)
		p++;
	return p - s;
}

int strcmp(const char *a, const char *b)
{
	while (*a && *a == *b)
		a++, b++;
	return (unsigned char)*a - (unsigned char)*b;
}

int strncmp(const char *a, const char *b, size_t n)
{
	for (; n; n--, a++, b++) {
		if (*a != *b)
			return (unsigned char)*a - (unsigned char)*b;
		if (!*a)
			break;
	}
	return 0;
}

char *strcpy(char *d, const char *s)
{
	char *r = d;
	while ((*d++ = *s++))
		;
	return r;
}

char *strchr(const char *s, int c)
{
	for (; *s; s++)
		if (*s == (char)c)
			return (char *)s;
	return c ? 0 : (char *)s;
}

/* bump allocator: free does nothing */
static char heap[1 << 20];
static size_t heap_used;

void *malloc(size_t n)
{
	void *p;
	n = (n + 15) & ~(size_t)15;
	if (heap_used + n > sizeof heap)
		return 0;
	p = heap + heap_used;
	heap_used += n;
	return p;
}

void *calloc(size_t a, size_t b)
{
	void *p = malloc(a * b);
	if (p)
		memset(p, 0, a * b);
	return p;
}

void free(void *p)
{
	(void)p;
}

void *realloc(void *p, size_t n)
{
	void *q = malloc(n);
	if (q && p)
		memcpy(q, p, n);
	return q;
}

extern void _exit(int);

void exit(int code)
{
	_exit(code);
}

void abort(void)
{
	_exit(134);
}

int abs(int x)
{
	return x < 0 ? -x : x;
}

static unsigned long seed = 1;

int rand(void)
{
	seed = seed * 1103515245 + 12345;
	return (seed >> 16) & 0x7fff;
}

void srand(unsigned s)
{
	seed = s;
}
