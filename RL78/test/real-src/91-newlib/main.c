/* Ghidra-Rare RL78 test program: links a broad slice of newlib (BSD-style licences) and libgcc
 * (runtime exception) into one image: formatted I/O, string conversion, sorting, malloc, libm
 * and 32/64-bit integer helpers. It is never run; it only has to be realistic compiler output. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

static int cmp_int(const void *a, const void *b)
{
	return *(const int *)a - *(const int *)b;
}

volatile long sink_l;
volatile long long sink_ll;
volatile double sink_d;
char buf[96];

int main(void)
{
	int v[8] = { 5, 3, 9, 1, 7, 2, 8, 4 };
	long a = strtol("123456", NULL, 10);
	unsigned long b = strtoul("0xdeadbeef", NULL, 16);
	long long c = (long long)a * (long long)b;
	char *p;

	qsort(v, 8, sizeof v[0], cmp_int);
	sniprintf(buf, sizeof buf, "%d %ld %lu %s", v[0], a, b, "x");
	sink_l = (long)strlen(buf) + a / (long)v[3] + (long)(b % 1000UL);
	sink_ll = c / 12345LL + (c >> 7);
	sink_d = sin(0.5) * sqrt((double)a) + (double)strtol("25", NULL, 8) + floor(3.7);
	p = malloc(16);
	if (p) {
		memcpy(p, buf, 15);
		p[15] = 0;
		sink_l += atoi(p);
		free(p);
	}
	return (int)sink_l;
}
