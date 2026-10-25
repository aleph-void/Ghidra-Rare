/* Disassemble the first instruction of every fixed-size slot of a raw file with GNU libopcodes.
 *   slotdis <bfd-arch[:mach]> <slot> <file> [-M options] [-f rl78_g10|rl78_g13|rl78_g14] [-e big]
 * Prints "<offset-hex> <len> <text>" per slot ("<offset> 0 (bad)" when libopcodes rejects it). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "bfd.h"
#include "dis-asm.h"

static char buf[512]; static size_t blen;
static int pf(void *s, const char *fmt, ...) { va_list ap; va_start(ap, fmt);
  int n = vsnprintf(buf + blen, sizeof buf - blen, fmt, ap); va_end(ap); if (n > 0) blen += n; return n; }
static int spf(void *s, enum disassembler_style st, const char *fmt, ...) { va_list ap; va_start(ap, fmt);
  int n = vsnprintf(buf + blen, sizeof buf - blen, fmt, ap); va_end(ap); if (n > 0) blen += n; return n; }
static void paddr(bfd_vma a, struct disassemble_info *i) { pf(0, "0x%lx", (unsigned long)a); }
extern int print_insn_rl78_g10(bfd_vma, disassemble_info *);
extern int print_insn_rl78_g13(bfd_vma, disassemble_info *);
extern int print_insn_rl78_g14(bfd_vma, disassemble_info *);

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "usage\n"); return 2; }
  const char *opts = NULL, *fn = NULL; int big = 0;
  for (int i = 4; i + 1 < argc; i += 2) {
    if (!strcmp(argv[i], "-M")) opts = argv[i + 1];
    else if (!strcmp(argv[i], "-f")) fn = argv[i + 1];
    else if (!strcmp(argv[i], "-e")) big = !strcmp(argv[i + 1], "big");
  }
  const bfd_arch_info_type *ai = bfd_scan_arch(argv[1]);
  if (!ai) { fprintf(stderr, "unknown arch %s\n", argv[1]); return 2; }
  int slot = atoi(argv[2]);
  FILE *f = fopen(argv[3], "rb"); fseek(f, 0, SEEK_END); long sz = ftell(f); rewind(f);
  unsigned char *data = malloc(sz); if (fread(data, 1, sz, f) != (size_t)sz) return 2; fclose(f);
  disassembler_ftype d = disassembler(ai->arch, big, ai->mach, NULL);
  if (fn) d = !strcmp(fn, "rl78_g10") ? print_insn_rl78_g10 : !strcmp(fn, "rl78_g13") ? print_insn_rl78_g13 : print_insn_rl78_g14;
  for (long off = 0; off + slot <= sz; off += slot) {
    struct disassemble_info info;
    init_disassemble_info(&info, NULL, pf, spf);
    info.arch = ai->arch; info.mach = ai->mach;
    info.endian = big ? BFD_ENDIAN_BIG : BFD_ENDIAN_LITTLE;
    info.buffer = data + off; info.buffer_vma = off; info.buffer_length = slot;
    info.print_address_func = paddr; info.disassembler_options = opts;
    disassemble_init_for_target(&info);
    blen = 0; buf[0] = 0;
    int n = d(off, &info);
    for (char *p = buf; *p; p++) if (*p == '\t' || *p == '\n') *p = ' ';
    if (n <= 0) printf("%08lx 0 (bad)\n", off); else printf("%08lx %d %s\n", off, n, buf);
  }
  return 0;
}
