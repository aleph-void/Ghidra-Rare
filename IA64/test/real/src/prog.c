/* Freestanding test program for the IA-64 module (built with GCC for ia64-linux-gnu and
 * ia64-hp-hpux11.23): integer and floating-point arithmetic, loops, a switch, structures,
 * recursion, many arguments and function pointers. */
typedef unsigned long size_t;

struct point { long x, y; double w; };

static long table[64];
volatile long sink;

long add3(long a, long b, long c) { return a + b + c; }

long many(long a, long b, long c, long d, long e, long f, long g, long h, long i, long j)
{
	return a - b + c * d - e + f * g - h + i * j;
}

long fib(long n) { return n < 2 ? n : fib(n - 1) + fib(n - 2); }

long mul_div(long a, long b) { return b ? (a * b) / (b + 3) + a % (b + 7) : 0; }

unsigned long umul_high(unsigned long a, unsigned long b)
{
	return (unsigned long)(((unsigned __int128)a * b) >> 64);
}

long sum_array(const long *p, size_t n)
{
	long s = 0;
	for (size_t i = 0; i < n; i++)
		s += p[i];
	return s;
}

void fill(long *p, size_t n, long v)
{
	for (size_t i = 0; i < n; i++)
		p[i] = v + (long)i;
}

int classify(int c)
{
	switch (c) {
	case 0: return 10;
	case 1: return 22;
	case 2: return 37;
	case 3: return 41;
	case 4: return 59;
	case 5: return 63;
	case 6: return 78;
	case 7: return 81;
	default: return -1;
	}
}

double dot(const double *a, const double *b, int n)
{
	double s = 0.0;
	for (int i = 0; i < n; i++)
		s += a[i] * b[i];
	return s;
}

double scale_point(struct point *p, double k)
{
	p->x = (long)(p->x * k);
	p->y = (long)(p->y * k);
	p->w = p->w * k + 1.0;
	return p->w / k;
}

float fsum(float a, float b, float c) { return a * b + c; }

long apply(long (*f)(long, long, long), long x) { return f(x, x + 1, x + 2); }

size_t my_strlen(const char *s)
{
	const char *p = s;
	while (*p)
		p++;
	return (size_t)(p - s);
}

void *my_memcpy(void *d, const void *s, size_t n)
{
	unsigned char *dp = d;
	const unsigned char *sp = s;
	while (n--)
		*dp++ = *sp++;
	return d;
}

long use_table(int i)
{
	table[i & 63] += i;
	return table[(i + 1) & 63];
}

long entry(void)
{
	long a[16];
	fill(a, 16, 3);
	struct point pt = { 3, 4, 2.5 };
	sink = sum_array(a, 16) + fib(10) + mul_div(100, 7) + classify(5) + apply(add3, 4) +
	       many(1, 2, 3, 4, 5, 6, 7, 8, 9, 10) + (long)scale_point(&pt, 2.0) + use_table(7) +
	       (long)umul_high(~0UL, 3);
	return sink;
}
