// Standalone driver for MAME's g65816 disassembler (src/devices/cpu/g65816/g65816ds.cpp,
// BSD-3-Clause, Karl Stenerud) with the M and X flags as options. unidasm hard-codes
// M=0 X=0, so it can only check 16-bit-mode decodes.
//
//   mame65816dis <file> [-m 0|1] [-x 0|1] [-basepc hex] [-track] [-stride n]
//   mame65816dis -list <file>     lines "<addr-hex> <m> <x> <bytes-hex>": decode each one
//
// Without -track every instruction is decoded with the given M/X (linear sweep). With -track
// the sweep follows REP/SEP immediates (and forces M=X=1 after "sec; xce"), which matches a
// linear reading of hand-written code. With -stride n one instruction is decoded at every
// n-byte record (corpus mode). Output: "<pc-hex6> <bytes> <text>".
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <sstream>
#include <string>
#include <vector>
#include "emu.h"
#include "g65816ds.h"

struct cfg : g65816_disassembler::config {
	bool m = false, x = false;
	bool get_m_flag() const override { return m; }
	bool get_x_flag() const override { return x; }
};

struct buf : util::disasm_interface::data_buffer {
	const std::vector<uint8_t> &d; uint32_t base;
	buf(const std::vector<uint8_t> &v, uint32_t b) : d(v), base(b) {}
	uint8_t g(uint32_t pc) const { uint32_t o = (pc - base) & 0xffffff; return o < d.size() ? d[o] : 0; }
	u8 r8(offs_t pc) const override { return g(pc); }
	u16 r16(offs_t pc) const override { return g(pc) | g(pc + 1) << 8; }
	u32 r32(offs_t pc) const override { return r16(pc) | uint32_t(r16(pc + 2)) << 16; }
	u64 r64(offs_t pc) const override { return r32(pc) | uint64_t(r32(pc + 4)) << 32; }
};

int main(int argc, char **argv) {
	if (argc == 3 && !strcmp(argv[1], "-list")) {
		FILE *lf = fopen(argv[2], "r");
		if (!lf) { perror(argv[2]); return 1; }
		char line[256];
		while (fgets(line, sizeof line, lf)) {
			unsigned addr; int m, x; char hex[64];
			if (sscanf(line, "%x %d %d %63s", &addr, &m, &x, hex) != 4) continue;
			std::vector<uint8_t> d;
			for (size_t k = 0; hex[k] && hex[k + 1]; k += 2) {
				unsigned v; sscanf(hex + k, "%2x", &v); d.push_back(v);
			}
			while (d.size() < 4) d.push_back(0);
			cfg c; c.m = m; c.x = x;
			g65816_disassembler dis(&c);
			buf b(d, addr);
			std::ostringstream s;
			uint32_t len = dis.disassemble(s, addr, b, b) & util::disasm_interface::LENGTHMASK;
			printf("%06x ", addr);
			for (uint32_t k = 0; k < len; k++) printf("%02x", d[k]);
			printf(" %s\n", s.str().c_str());
		}
		return 0;
	}
	if (argc < 2) { fprintf(stderr, "usage: %s file [-m 0|1] [-x 0|1] [-basepc hex] [-track]\n", argv[0]); return 2; }
	cfg c; uint32_t base = 0; bool track = false; uint32_t stride = 0;
	for (int i = 2; i < argc; i++) {
		if (!strcmp(argv[i], "-m")) c.m = atoi(argv[++i]);
		else if (!strcmp(argv[i], "-x")) c.x = atoi(argv[++i]);
		else if (!strcmp(argv[i], "-basepc")) base = strtoul(argv[++i], nullptr, 16);
		else if (!strcmp(argv[i], "-track")) track = true;
		else if (!strcmp(argv[i], "-stride")) stride = atoi(argv[++i]);
	}
	FILE *f = fopen(argv[1], "rb");
	if (!f) { perror(argv[1]); return 1; }
	std::vector<uint8_t> d; int ch;
	while ((ch = fgetc(f)) != EOF) d.push_back(ch);
	fclose(f);
	g65816_disassembler dis(&c);
	buf b(d, base);
	bool carry_set = false;
	for (uint32_t off = 0; off < d.size();) {
		uint32_t pc = base + off;
		std::ostringstream s;
		uint32_t len = dis.disassemble(s, pc, b, b) & util::disasm_interface::LENGTHMASK;
		printf("%06x ", pc);
		for (uint32_t k = 0; k < len; k++) printf("%02x", b.g(pc + k));
		printf(" %s\n", s.str().c_str());
		if (track) {
			uint8_t op = b.g(pc), imm = b.g(pc + 1);
			if (op == 0xc2) { if (imm & 0x20) c.m = false; if (imm & 0x10) c.x = false; }
			if (op == 0xe2) { if (imm & 0x20) c.m = true; if (imm & 0x10) c.x = true; }
			if (op == 0x18) carry_set = false;
			if (op == 0x38) carry_set = true;
			if (op == 0xfb && carry_set) c.m = c.x = true;
		}
		off += stride ? stride : len;
	}
	return 0;
}
