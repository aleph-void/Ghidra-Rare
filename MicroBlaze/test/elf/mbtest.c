/* Reference C source for test/elf/mbtest.s (hand-compiled to MicroBlaze assembly in the style of
 * microblaze-elf-gcc -O2). No MicroBlaze C compiler is required. */

typedef unsigned int u32;
typedef unsigned long long u64;

int global_counter;
static const char message[] = "hello, microblaze";
volatile u32 *const uart = (volatile u32 *)0x40600004;

int add3(int a, int b, int c)
{
	return a + b + c;
}

u32 checksum(const unsigned char *p, int n)
{
	u32 s = 0;
	for (int i = 0; i < n; i++)
		s = (s << 5) + s + p[i];
	return s;
}

int strlen_local(const char *s)
{
	int n = 0;
	while (s[n])
		n++;
	return n;
}

int classify(int x)
{
	switch (x) {
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

u64 add64(u64 a, u64 b)
{
	return a + b + 0x123456789abcdefULL;
}

int many_args(int a, int b, int c, int d, int e, int f, int g, int h)
{
	return a - b + c - d + e - f + g * h;
}

void uart_puts(const char *s)
{
	while (*s)
		*uart = (u32)*s++;
}

int call_chain(int x)
{
	global_counter += add3(x, 1, 2);
	return many_args(x, 1, 2, 3, 4, 5, 6, 7) + classify(x & 7);
}

int main(void)
{
	uart_puts(message);
	return call_chain(strlen_local(message)) + (int)checksum((const unsigned char *)message, 5);
}

void _start(void)
{
	main();
	for (;;)
		;
}
