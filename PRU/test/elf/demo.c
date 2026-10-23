/* Small PRU firmware used to sanity-check ELF import, analysis and decompilation. */
#include <stdint.h>

volatile register uint32_t __R30;
volatile register uint32_t __R31;

#define SHARED ((volatile uint32_t *)0x00010000)

/* PRU-ICSS INTC through constant-table entry C0 (LBCO/SBCO) */
typedef struct {
	uint32_t REVID;
	uint32_t CR;
	uint32_t rsvd[2];
	uint32_t GER;
	uint32_t rsvd2[4];
	uint32_t SISR;
} intc_t;
volatile __far intc_t CT_INTC __attribute__((cregister("PRU_INTC", far), peripheral));

const uint8_t lut[8] = { 3, 1, 4, 1, 5, 9, 2, 6 };

uint32_t table[16];

uint32_t checksum(const uint8_t *p, uint32_t n)
{
	uint32_t s = 0, i;
	for (i = 0; i < n; i++)
		s = (s << 1) ^ p[i];
	return s;
}

int clamp(int v, int lo, int hi)
{
	if (v < lo)
		return lo;
	if (v > hi)
		return hi;
	return v;
}

uint32_t highbit(uint32_t x)
{
	return 31 - __lmbd(x, 1) ;
}

void fill_table(uint32_t seed)
{
	int i;
	for (i = 0; i < 16; i++) {
		seed = seed * 1103515245u + 12345u;
		table[i] = seed >> 16;
	}
}

void wait_and_toggle(void)
{
	while ((__R31 & (1u << 30)) == 0)
		;
	__R30 ^= 1u << 5;
}

uint32_t dispatch(uint32_t op, uint32_t a, uint32_t b)
{
	switch (op) {
	case 0: return a + b;
	case 1: return a - b;
	case 2: return a & b;
	case 3: return a | b;
	case 4: return a ^ b;
	case 5: return a << (b & 31);
	case 6: return a >> (b & 31);
	case 7: return lut[a & 7];
	default: return 0;
	}
}

void raise_event(uint32_t ev)
{
	CT_INTC.GER = 1;
	CT_INTC.SISR = ev;
}

extern uint32_t asm_sum_shared(uint32_t n);
extern void asm_intc_ack(uint32_t ev);

int main(void)
{
	uint32_t c;
	fill_table(SHARED[0]);
	c = checksum((const uint8_t *)table, sizeof(table));
	SHARED[1] = c;
	SHARED[2] = clamp((int)SHARED[3], -5, 100);
	SHARED[4] = highbit(c);
	SHARED[5] = dispatch(SHARED[6], SHARED[7], SHARED[8]);
	raise_event(SHARED[9]);
	SHARED[10] = asm_sum_shared(8);
	asm_intc_ack(SHARED[11]);
	wait_and_toggle();
	__halt();
	return 0;
}
