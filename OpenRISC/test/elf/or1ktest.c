/* OpenRISC test program for the Ghidra module: compiled with the optional ISA extensions
 * (hard float incl. ORFPX64A32 doubles, cmov, sext, ror/rori, set-flag immediates, shift
 * immediates) so that the ELF exercises them. See build.sh. Public domain. */
typedef unsigned int u32;
typedef unsigned long long u64;

volatile u32 mmio_out;
int table[8] = { 3, 1, 4, 1, 5, 9, 2, 6 };
struct point { int x, y; float w; double d; };

int add3(int a, int b, int c) { return a + b + c; }

u64 add64(int p, u64 x) { return x + (u64)p * 3; }

u32 rotr(u32 v, int n) { return (v >> n) | (v << ((32 - n) & 31)); }

u32 rotr7(u32 v) { return (v >> 7) | (v << 25); }

int smax(int a, int b) { return a > b ? a : b; }

int sext16(int v) { return (short)v + (signed char)(v >> 8); }

int sum_table(int n)
{
	int s = 0;
	for (int i = 0; i < n && i < 8; i++)
		s += table[i];
	return s;
}

int classify(int k)
{
	switch (k) {
	case 0: return 11;
	case 1: return 23;
	case 2: return 35;
	case 3: return 47;
	case 4: return 59;
	case 5: return 61;
	case 6: return 73;
	default: return -1;
	}
}

float fmix(float a, float b, int i) { return a * b + (float)i - a / b; }

double dmix(double a, double b, float c) { return a * b - (double)c + a / b; }

int dcmp(double a, double b) { return a < b ? (int)a : (int)(a - b); }

float fpoint(struct point *p) { return p->w * (float)p->x + (float)p->y + (float)p->d; }

void store(u32 v) { mmio_out = v; mmio_out = v >> 16; }

u64 mul64(u64 a, u64 b) { return a * b; }

int divs(int a, int b) { return a / b + a % b; }

void _start(void)
{
	struct point pt = { 1, 2, 3.0f, 4.0 };
	int r = add3(1, 2, 3) + (int)add64(4, 5) + rotr(6, 7) + rotr7(8) + smax(9, 10) +
		sext16(11) + sum_table(12) + classify(r) + (int)fmix(1.0f, 2.0f, 3) +
		(int)dmix(4.0, 5.0, 6.0f) + dcmp(7.0, 8.0) + (int)fpoint(&pt) + (int)mul64(9, 10) +
		divs(11, 12);
	store(r);
	for (;;)
		;
}
