/* Integer division helpers the GCC i860 port calls as .div, .udiv, .rem and .urem (the System V
 * i860 libc provided them). Shift-and-subtract; written for this module (MIT). divide.s
 * gives them their dotted names. */
unsigned i860_udiv(unsigned n, unsigned d)
{
	unsigned q = 0, r = 0;
	int i;
	for (i = 31; i >= 0; i--) {
		r = (r << 1) | ((n >> i) & 1);
		if (r >= d) {
			r -= d;
			q |= 1u << i;
		}
	}
	return q;
}

unsigned i860_urem(unsigned n, unsigned d)
{
	return n - i860_udiv(n, d) * d;
}

int i860_div(int n, int d)
{
	unsigned q = i860_udiv(n < 0 ? -n : n, d < 0 ? -d : d);
	return (n < 0) != (d < 0) ? -(int)q : (int)q;
}

int i860_rem(int n, int d)
{
	return n - i860_div(n, d) * d;
}
