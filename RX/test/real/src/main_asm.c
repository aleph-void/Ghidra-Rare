/* Calls the hand-written RXv2/RXv3 routines (dsp_v2.s, dfpu_v3.s). */
#include <stdio.h>
extern int fir_q15(const short *x, const short *h, int n);
extern int atomic_add(int *p, int v);
extern long long mac64(int a, int b, long long acc);
extern float fdist(float x, float y);
extern unsigned to_unsigned(float f);
#ifdef V3
extern int dpoly(const double *c, int n, const double *x);
extern unsigned bf(unsigned a, unsigned b);
extern unsigned x3(unsigned a, unsigned b);
#endif
static short xs[8] = { 1000, -2000, 3000, -4000, 5000, -6000, 7000, -8000 };
static short hs[8] = { 16384, 8192, 4096, 2048, 1024, 512, 256, 128 };
int counter;
int main(void)
{
	printf("%d\n", fir_q15(xs, hs, 8));
	printf("%d\n", atomic_add(&counter, 5));
	printf("%lld\n", mac64(1000, -3000, 77));
	printf("%f %u\n", (double)fdist(3.0f, 4.0f), to_unsigned(3e9f));
#ifdef V3
	static const double c[3] = { 1.0, 2.0, 3.0 };
	double x = 2.0;
	printf("%d %u %u\n", dpoly(c, 3, &x), bf(0xabc, 0xffffffff), x3(0xf0f0, 0xff00));
#endif
	return 0;
}
