/* zlib round trip for the bare-metal i860 test programs (written for this module, MIT). */
#include <string.h>
#include <stdlib.h>
#include "zlib.h"

/* built with Z_SOLO: the allocator is supplied by the caller */
static voidpf zalloc(voidpf opaque, uInt items, uInt size)
{
	(void)opaque;
	return calloc(items, size);
}

static void zfree(voidpf opaque, voidpf p)
{
	(void)opaque;
	free(p);
}

static unsigned char src[8192], comp[9000], back[8192];

int main(void)
{
	z_stream s;
	unsigned i, n;
	for (i = 0; i < sizeof src; i++)
		src[i] = (unsigned char)((i * 7) ^ (i >> 5));
	memset(&s, 0, sizeof s);
	s.zalloc = zalloc;
	s.zfree = zfree;
	if (deflateInit(&s, 9) != Z_OK)
		return 1;
	s.next_in = src;
	s.avail_in = sizeof src;
	s.next_out = comp;
	s.avail_out = sizeof comp;
	if (deflate(&s, Z_FINISH) != Z_STREAM_END)
		return 2;
	n = sizeof comp - s.avail_out;
	deflateEnd(&s);
	memset(&s, 0, sizeof s);
	s.zalloc = zalloc;
	s.zfree = zfree;
	if (inflateInit(&s) != Z_OK)
		return 3;
	s.next_in = comp;
	s.avail_in = n;
	s.next_out = back;
	s.avail_out = sizeof back;
	if (inflate(&s, Z_FINISH) != Z_STREAM_END)
		return 4;
	inflateEnd(&s);
	return memcmp(src, back, sizeof src) != 0 ? 5 : (int)(adler32(0, back, sizeof back) & 0x7f);
}
