/* Test program for the RX module's real-code check: exercises integer, floating-point, string,
 * stdio, stdlib and math code from newlib so the linked image contains a broad mix of
 * compiler-generated RX code. */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct rec {
	char name[16];
	int key;
	double weight;
};

static int cmp_rec(const void *a, const void *b)
{
	const struct rec *x = a, *y = b;
	if (x->key != y->key)
		return x->key < y->key ? -1 : 1;
	return strcmp(x->name, y->name);
}

static uint32_t crc32_bitwise(const uint8_t *p, size_t n)
{
	uint32_t c = 0xffffffffu;
	while (n--) {
		c ^= *p++;
		for (int k = 0; k < 8; k++)
			c = (c >> 1) ^ (0xedb88320u & -(c & 1));
	}
	return ~c;
}

static int64_t mul64(int64_t a, int64_t b) { return a * b; }
static uint64_t div64(uint64_t a, uint64_t b) { return b ? a / b : 0; }

static float poly(float x)
{
	return ((0.5f * x - 1.25f) * x + 2.0f) * x - 3.0f;
}

static int switch_test(int v)
{
	switch (v) {
	case 0: return 10;
	case 1: return 22;
	case 2: return 37;
	case 3: return 41;
	case 4: return 59;
	case 5: return 63;
	case 6: return 78;
	default: return -1;
	}
}

volatile int sink;

int main(int argc, char **argv)
{
	static struct rec recs[8];
	char buf[128];
	for (int i = 0; i < 8; i++) {
		snprintf(recs[i].name, sizeof recs[i].name, "item%02d", (i * 5) % 8);
		recs[i].key = (i * 7) % 5;
		recs[i].weight = sqrt((double)i) * 1.5;
	}
	qsort(recs, 8, sizeof recs[0], cmp_rec);
	for (int i = 0; i < 8; i++)
		printf("%s %d %.3f\n", recs[i].name, recs[i].key, recs[i].weight);
	struct rec key = { "item03", 0, 0 };
	key.key = recs[3].key;
	struct rec *f = bsearch(&key, recs, 8, sizeof recs[0], cmp_rec);
	printf("found %p\n", (void *)f);
	strcpy(buf, "The quick brown fox jumps over the lazy dog");
	printf("crc %08lx len %u\n", (unsigned long)crc32_bitwise((uint8_t *)buf, strlen(buf)),
		(unsigned)strlen(buf));
	char *tok = strtok(buf, " ");
	while (tok) {
		sink += (int)strlen(tok);
		tok = strtok(NULL, " ");
	}
	printf("%lld %llu\n", (long long)mul64(123456789, -987654321), (unsigned long long)div64(1ull << 50, 12345));
	double d = strtod("2.718281828", NULL);
	printf("%g %g %g %g\n", sin(d), cos(d), pow(d, 3.5), atan2(d, 1.0));
	printf("%f %d\n", (double)poly((float)argc), switch_test(argc));
	char *m = malloc(256);
	if (m) {
		memset(m, 'x', 255);
		m[255] = 0;
		sink += (int)strlen(m);
		free(m);
	}
	int a, b;
	if (sscanf("12 34", "%d %d", &a, &b) == 2)
		printf("%d\n", a * b);
	return 0;
}
