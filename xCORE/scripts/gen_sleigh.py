#!/usr/bin/env python3
"""Generate the xCORE SLEIGH specifications (XS1, XS2, XS3) from the encoding tables.

    python3 scripts/gen_sleigh.py            # writes data/languages/xcore_xs{1,2,3}.slaspec

Encodings come from isa_tables.py (transcribed from the XMOS architecture manuals); the
assembly syntax follows the XMOS assembler / LLVM XCore disassembler conventions and the
semantics are written per instruction below (SPEC).
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from isa_tables import ENC  # noqa: E402

BITP = [32, 1, 2, 3, 4, 5, 6, 7, 8, 16, 24, 32]

# ---------------------------------------------------------------------------------------
# Instruction specification: NAME -> (assembly template, semantics, operand-kind overrides)
#   {n} in the template / semantics is the doc operand opN.
#   kinds: r = r0..r11 register, R = r0..r11,cp,dp,sp,lr (4-bit field), us = 0..11 immediate,
#          bp = bit position immediate, u = plain immediate, rn = register number (constant),
#          brf/brb = forward/backward pc-relative branch target, apf/apb = pc-relative address.
# ---------------------------------------------------------------------------------------
LD32 = '*:4 ({a})'


def mem(a):
    return '*:4 (%s)' % a


SPEC = {
    # ---- integer arithmetic / logic ----------------------------------------------------
    'ADD': ('add {1}, {2}, {3}', '{1} = {2} + {3};', {}),
    'ADDI': ('add {1}, {2}, {3}', '{1} = {2} + {3};', {}),
    'SUB': ('sub {1}, {2}, {3}', '{1} = {2} - {3};', {}),
    'SUBI': ('sub {1}, {2}, {3}', '{1} = {2} - {3};', {}),
    'AND': ('and {1}, {2}, {3}', '{1} = {2} & {3};', {}),
    'OR': ('or {1}, {2}, {3}', '{1} = {2} | {3};', {}),
    'XOR': ('xor {1}, {2}, {3}', '{1} = {2} ^ {3};', {}),
    'XOR4': ('xor4 {1}, {4}, {2}, {3}, {5}', '{1} = {2} ^ {3} ^ {4} ^ {5};', {}),
    'EQ': ('eq {1}, {2}, {3}', '{1} = zext({2} == {3});', {}),
    'EQI': ('eq {1}, {2}, {3}', '{1} = zext({2} == {3});', {}),
    'LSS': ('lss {1}, {2}, {3}', '{1} = zext({2} s< {3});', {}),
    'LSU': ('lsu {1}, {2}, {3}', '{1} = zext({2} < {3});', {}),
    'SHL': ('shl {1}, {2}, {3}', '{1} = {2} << {3};', {}),
    'SHLI': ('shl {1}, {2}, {3}', '{1} = {2} << {3};', {3: 'bp'}),
    'SHR': ('shr {1}, {2}, {3}', '{1} = {2} >> {3};', {}),
    'SHRI': ('shr {1}, {2}, {3}', '{1} = {2} >> {3};', {3: 'bp'}),
    'ASHR': ('ashr {1}, {2}, {3}', '{1} = {2} s>> {3};', {}),
    'ASHRI': ('ashr {1}, {2}, {3}', '{1} = {2} s>> {3};', {3: 'bp'}),
    'MUL': ('mul {1}, {2}, {3}', '{1} = {2} * {3};', {}),
    'DIVS': ('divs {1}, {2}, {3}', '{1} = {2} s/ {3};', {}),
    'DIVU': ('divu {1}, {2}, {3}', '{1} = {2} / {3};', {}),
    'REMS': ('rems {1}, {2}, {3}', '{1} = {2} s% {3};', {}),
    'REMU': ('remu {1}, {2}, {3}', '{1} = {2} % {3};', {}),
    'NOT': ('not {1}, {2}', '{1} = ~{2};', {}),
    'NEG': ('neg {1}, {2}', '{1} = -{2};', {}),
    'ANDNOT': ('andnot {1}, {2}', '{1} = {1} & ~{2};', {}),
    'MKMSK': ('mkmsk {1}, {2}', '{1} = (1 << {2}) - 1;', {}),
    'MKMSKI': ('mkmsk {1}, {2}', '{1} = (1 << {2}) - 1;', {2: 'bp'}),
    'SEXT': ('sext {1}, {2}',
             'local n:4 = {2}; if (n s<= 0 || n s>= 32) goto <done>; local sh:4 = 32 - n; '
             '{1} = ({1} << sh) s>> sh; <done>', {}),
    'SEXTI': ('sext {1}, {2}',
              'local n:4 = {2}; if (n s<= 0 || n s>= 32) goto <done>; local sh:4 = 32 - n; '
              '{1} = ({1} << sh) s>> sh; <done>', {2: 'bp'}),
    'ZEXT': ('zext {1}, {2}',
             'local n:4 = {2}; if (n s<= 0 || n s>= 32) goto <done>; '
             '{1} = {1} & ((1 << n) - 1); <done>', {}),
    'ZEXTI': ('zext {1}, {2}',
              'local n:4 = {2}; if (n s<= 0 || n s>= 32) goto <done>; '
              '{1} = {1} & ((1 << n) - 1); <done>', {2: 'bp'}),
    'CLZ': ('clz {1}, {2}', '{1} = lzcount({2});', {}),
    'CLS': ('cls {1}, {2}', '{1} = lzcount({2} ^ ({2} s>> 31));', {}),
    'BITREV': ('bitrev {1}, {2}',
               'local x:4 = {2}; '
               'x = ((x >> 1) & 0x55555555) | ((x & 0x55555555) << 1); '
               'x = ((x >> 2) & 0x33333333) | ((x & 0x33333333) << 2); '
               'x = ((x >> 4) & 0x0f0f0f0f) | ((x & 0x0f0f0f0f) << 4); '
               'x = ((x >> 8) & 0x00ff00ff) | ((x & 0x00ff00ff) << 8); '
               '{1} = (x >> 16) | (x << 16);', {}),
    'BYTEREV': ('byterev {1}, {2}',
                'local x:4 = {2}; {1} = (x >> 24) | ((x >> 8) & 0xff00) | ((x << 8) & 0xff0000) | (x << 24);',
                {}),
    # ---- long arithmetic --------------------------------------------------------------
    'LADD': ('ladd {4}, {1}, {2}, {3}, {5}',
             'local r:8 = zext({2}) + zext({3}) + zext({5} & 1); {1} = r:4; {4} = r(4);', {}),
    'LSUB': ('lsub {4}, {1}, {2}, {3}, {5}',
             'local r:8 = zext({2}) - zext({3}) - zext({5} & 1); {1} = r:4; {4} = r(4) & 1;', {}),
    'LDIVU': ('ldivu {1}, {4}, {5}, {2}, {3}',
              'local n:8 = (zext({5}) << 32) | zext({2}); local dv:8 = zext({3}); '
              'local q:8 = n / dv; local m:8 = n % dv; {1} = q:4; {4} = m:4;', {}),
    'LMUL': ('lmul {1}, {4}, {2}, {3}, {5}, {6}',
             'local r:8 = zext({2}) * zext({3}) + zext({5}) + zext({6}); {4} = r:4; {1} = r(4);', {}),
    'MACCU': ('maccu {1}, {4}, {2}, {3}',
              'local r:8 = ((zext({1}) << 32) | zext({4})) + zext({2}) * zext({3}); {4} = r:4; {1} = r(4);',
              {}),
    'MACCS': ('maccs {1}, {4}, {2}, {3}',
              'local r:8 = ((zext({1}) << 32) | zext({4})) + sext({2}) * sext({3}); {4} = r:4; {1} = r(4);',
              {}),
    'LSATS': ('lsats {1}, {2}, {3}',
              'local v:8 = (zext({1}) << 32) | zext({2}); local hi:8 = (1 << (zext({3}) + 32)) - 1; '
              'local lo:8 = -(1 << (zext({3}) + 32)); '
              'if (v s<= hi) goto <a>; v = hi; <a> if (v s>= lo) goto <b>; v = lo; <b> '
              '{1} = v(4); {2} = v:4;', {}),
    'LEXTRACT': ('lextract {1}, {4}, {2}, {3}, {5}',
                 'local t:8 = (zext({4}) << 32) | zext({2}); t = t >> zext({3}); '
                 '{1} = t:4 & ((1 << {5}) - 1);', {5: 'bp'}),
    'LINSERT': ('linsert {1}, {4}, {2}, {3}, {5}',
                'local m:8 = ((1 << zext({5})) - 1) << zext({3}); local t:8 = (zext({1}) << 32) | zext({4}); '
                't = (t & ~m) | ((zext({2}) << zext({3})) & m); {1} = t(4); {4} = t:4;', {5: 'bp'}),
    'CRC': ('crc32 {1}, {2}, {3}', '{1} = crc32({1}, {2}, {3});', {}),
    'CRC8': ('crc8 {4}, {1}, {2}, {3}', '{4} = crc8({4}, {2}, {3}); {1} = {2} >> 8;', {}),
    # CRCN / CRC32_INC operand order and roles checked against lib_xud's XUD_Token_In_DI.S as
    # assembled in the sw_usb_audio 8.1.0 release: "crcn crc, data, poly, nbits" (crc is in the
    # high-half register field, unlike the manual's op numbering) and
    # "crc32_inc crc, data, poly, idx, bitp".
    'CRCN': ('crcn {4}, {1}, {2}, {3}', '{4} = crcn({4}, {1}, {2}, {3});', {}),
    'CRC32_INC': ('crc32_inc {1}, {2}, {3}, {4}, {5}',
                  '{1} = crc32({1}, {2}, {3}); {4} = {4} + {5};', {5: 'bp'}),
    'ZIP': ('zip {1}, {2}, {3}', 'local z:8 = zip({1}, {2}, {3}); {1} = z(4); {2} = z:4;', {}),
    'UNZIP': ('unzip {1}, {2}, {3}', 'local z:8 = unzip({1}, {2}, {3}); {1} = z(4); {2} = z:4;', {}),
    # ---- floating point (XS3) ---------------------------------------------------------
    'FADD': ('fadd {1}, {2}, {3}', '{1} = {2} f+ {3};', {}),
    'FSUB': ('fsub {1}, {2}, {3}', '{1} = {2} f- {3};', {}),
    'FMUL': ('fmul {1}, {2}, {3}', '{1} = {2} f* {3};', {}),
    'FMACC': ('fmacc {4}, {1}, {2}, {3}', '{4} = {1} f+ ({2} f* {3});', {}),
    'FEQ': ('feq {1}, {2}, {3}', '{1} = zext({2} f== {3});', {}),
    'FLT': ('flt {1}, {2}, {3}', '{1} = zext({2} f< {3});', {}),
    'FGT': ('fgt {1}, {2}, {3}', '{1} = zext({2} f> {3});', {}),
    'FUN': ('fun {1}, {2}, {3}', '{1} = zext(nan({2}) || nan({3}));', {}),
    'FSEXP': ('fsexp {1}, {2}, {3}', '{1} = {3} >> 31; {2} = fsexp_exp({3});', {}),
    'FMANT': ('fmant {1}, {2}', '{1} = fmant({2});', {}),
    'FSPEC': ('fspec {1}, {2}', '{1} = fspec({2});', {}),
    'FMAKE': ('fmake {1}, {4}, {2}, {3}, {5}', '{1} = fmake({4}, {2}, {3}, {5});', {}),
    'FENAN': ('fenan {1}', 'fenan({1});', {}),
    # ---- loads / stores ---------------------------------------------------------------
    'LDW': ('ldw {1}, {2}[{3}]', '{1} = *:4 ({2} + {3} * 4);', {}),
    'LDWI': ('ldw {1}, {2}[{3}]', '{1} = *:4 ({2} + {3} * 4);', {}),
    'LD16S': ('ld16s {1}, {2}[{3}]', '{1} = sext(*:2 ({2} + {3} * 2));', {}),
    'LD8U': ('ld8u {1}, {2}[{3}]', '{1} = zext(*:1 ({2} + {3}));', {}),
    'STW': ('stw {1}, {2}[{3}]', '*:4 ({2} + {3} * 4) = {1};', {}),
    'STWI': ('stw {1}, {2}[{3}]', '*:4 ({2} + {3} * 4) = {1};', {}),
    'ST16': ('st16 {1}, {2}[{3}]', '*:2 ({2} + {3} * 2) = {1}:2;', {}),
    'ST8': ('st8 {1}, {2}[{3}]', '*:1 ({2} + {3}) = {1}:1;', {}),
    'LDD': ('ldd {4}, {1}, {2}[{3}]',
            'local a:4 = {2} + {3} * 8; {1} = *:4 a; {4} = *:4 (a + 4);', {}),
    'LDDI': ('ldd {4}, {1}, {2}[{3}]',
             'local a:4 = {2} + {3} * 8; {1} = *:4 a; {4} = *:4 (a + 4);', {}),
    'STD': ('std {4}, {1}, {2}[{3}]',
            'local a:4 = {2} + {3} * 8; *:4 a = {1}; *:4 (a + 4) = {4};', {}),
    'STDI': ('std {4}, {1}, {2}[{3}]',
             'local a:4 = {2} + {3} * 8; *:4 a = {1}; *:4 (a + 4) = {4};', {}),
    'LDDSP': ('ldd {2}, {1}, sp[{3}]',
              'local a:4 = sp + {3} * 8; {1} = *:4 a; {2} = *:4 (a + 4);', {}),
    'STDSP': ('std {2}, {1}, sp[{3}]',
              'local a:4 = sp + {3} * 8; *:4 a = {1}; *:4 (a + 4) = {2};', {}),
    'LDAWF': ('ldaw {1}, {2}[{3}]', '{1} = {2} + {3} * 4;', {}),
    'LDAWFI': ('ldaw {1}, {2}[{3}]', '{1} = {2} + {3} * 4;', {}),
    'LDAWB': ('ldaw {1}, {2}[-{3}]', '{1} = {2} - {3} * 4;', {}),
    'LDAWBI': ('ldaw {1}, {2}[-{3}]', '{1} = {2} - {3} * 4;', {}),
    'LDA16F': ('lda16 {1}, {2}[{3}]', '{1} = {2} + {3} * 2;', {}),
    'LDA16B': ('lda16 {1}, {2}[-{3}]', '{1} = {2} - {3} * 2;', {}),
    'LDWDP': ('ldw {1}, dp[{2}]', '{1} = *:4 (dp + {2} * 4);', {}),
    'STWDP': ('stw {1}, dp[{2}]', '*:4 (dp + {2} * 4) = {1};', {}),
    'LDWSP': ('ldw {1}, sp[{2}]', '{1} = *:4 (sp + {2} * 4);', {}),
    'STWSP': ('stw {1}, sp[{2}]', '*:4 (sp + {2} * 4) = {1};', {}),
    'LDWCP': ('ldw {1}, cp[{2}]', '{1} = *:4 (cp + {2} * 4);', {}),
    'LDWCPL': ('ldw r11, cp[{1}]', 'r11 = *:4 (cp + {1} * 4);', {}),
    'LDAWDP': ('ldaw {1}, dp[{2}]', '{1} = dp + {2} * 4;', {}),
    'LDAWSP': ('ldaw {1}, sp[{2}]', '{1} = sp + {2} * 4;', {}),
    'LDAWCP': ('ldaw r11, cp[{1}]', 'r11 = cp + {1} * 4;', {}),
    'LDC': ('ldc {1}, {2}', '{1} = {2};', {}),
    'LDAPF': ('ldap r11, {1}', 'r11 = {1};', {1: 'apf'}),
    'LDAPB': ('ldap r11, {1}', 'r11 = {1};', {1: 'apb'}),
    'LDET': ('ldw et, sp[4]', 'et = *:4 (sp + 16);', {}),
    'LDSED': ('ldw sed, sp[3]', 'sed = *:4 (sp + 12);', {}),
    'LDSPC': ('ldw spc, sp[1]', 'spc = *:4 (sp + 4);', {}),
    'LDSSR': ('ldw ssr, sp[2]', 'ssr = *:4 (sp + 8);', {}),
    'STET': ('stw et, sp[4]', '*:4 (sp + 16) = et;', {}),
    'STSED': ('stw sed, sp[3]', '*:4 (sp + 12) = sed;', {}),
    'STSPC': ('stw spc, sp[1]', '*:4 (sp + 4) = spc;', {}),
    'STSSR': ('stw ssr, sp[2]', '*:4 (sp + 8) = ssr;', {}),
    # ---- stack / pointer registers -----------------------------------------------------
    'ENTSP': ('entsp {1}', 'ENTSP', {}),
    'DUALENTSP': ('dualentsp {1}', 'DUALENTSP', {}),
    'RETSP': ('retsp {1}', 'RETSP', {}),
    'EXTSP': ('extsp {1}', 'sp = sp - {1} * 4;', {}),
    'EXTDP': ('extdp {1}', 'dp = dp - {1} * 4;', {}),
    'KENTSP': ('kentsp {1}', '*:4 ksp = sp; sp = ksp - {1} * 4;', {}),
    'KRESTSP': ('krestsp {1}', 'ksp = sp + {1} * 4; sp = *:4 ksp;', {}),
    'SETSP': ('set sp, {1}', 'sp = {1};', {}),
    'SETDP': ('set dp, {1}', 'dp = {1};', {}),
    'SETCP': ('set cp, {1}', 'cp = {1};', {}),
    'SETKEP': ('set kep, r11', 'kep = r11;', {}),
    'GETKEP': ('get r11, kep', 'r11 = kep;', {}),
    'GETKSP': ('get r11, ksp', 'r11 = ksp;', {}),
    'GETED': ('get r11, ed', 'r11 = ed;', {}),
    'GETET': ('get r11, et', 'r11 = et;', {}),
    'GETID': ('get r11, id', 'r11 = getid();', {}),
    'SETSR': ('setsr {1}', 'sr = sr | {1};', {}),
    'CLRSR': ('clrsr {1}', 'sr = sr & ~{1};', {}),
    'GETSR': ('getsr r11, {1}', 'r11 = sr & {1};', {}),
    # ---- branches / calls ------------------------------------------------------------
    'BRFT': ('bt {1}, {2}', 'if ({1} != 0) goto {2};', {1: 'r', 2: 'brf'}),
    'BRBT': ('bt {1}, {2}', 'if ({1} != 0) goto {2};', {1: 'r', 2: 'brb'}),
    'BRFF': ('bf {1}, {2}', 'if ({1} == 0) goto {2};', {1: 'r', 2: 'brf'}),
    'BRBF': ('bf {1}, {2}', 'if ({1} == 0) goto {2};', {1: 'r', 2: 'brb'}),
    'BRFU': ('bu {1}', 'goto {1};', {1: 'brf'}),
    'BRBU': ('bu {1}', 'goto {1};', {1: 'brb'}),
    'BRU': ('bru {1}', 'BRU', {}),
    'BAU': ('bau {1}', 'goto [{1}];', {}),
    'BLRF': ('bl {1}', 'lr = inst_next; call {1};', {1: 'brf'}),
    'BLRB': ('bl {1}', 'lr = inst_next; call {1};', {1: 'brb'}),
    'BLA': ('bla {1}', 'lr = inst_next; call [{1}];', {}),
    'BLACP': ('bla cp[{1}]', 'lr = inst_next; local t:4 = *:4 (cp + {1} * 4); call [t];', {}),
    'BLAT': ('blat {1}', 'lr = inst_next; local t:4 = *:4 (r11 + {1} * 4); call [t];', {}),
    'KCALL': ('kcall {1}', 'spc = inst_next; ssr = sr; sed = ed; ed = {1}; et = 15; kcall({1});', {}),
    'KCALLI': ('kcall {1}', 'spc = inst_next; ssr = sr; sed = ed; ed = {1}; et = 15; kcall({1});', {}),
    'KRET': ('kret', 'sr = ssr; ed = sed; return [spc];', {}),
    'ECALLT': ('ecallt {1}', 'if ({1} == 0) goto <done>; raise_exception({1}); <done>', {}),
    'ECALLF': ('ecallf {1}', 'if ({1} != 0) goto <done>; raise_exception({1}); <done>', {}),
    'ELATE': ('elate {1}', 'elate({1});', {}),
    'DCALL': ('dcall', 'dspc = inst_next; dssr = sr; dcall();', {}),
    'DRET': ('dret', 'sr = dssr; return [dspc];', {}),
    'DENTSP': ('dentsp', 'dssp = sp; sp = dentsp_ramend();', {}),
    'DRESTSP': ('drestsp', 'sp = dssp;', {}),
    'DGETREG': ('dgetreg {1}', '{1} = dgetreg();', {}),
    'NOP': ('nop', '', {}),
    'FLUSH': ('flush', 'cache_flush();', {}),
    'INVALIDATE': ('invalidate', 'cache_invalidate();', {}),
    'PREFETCH': ('prefetch r11', 'prefetch(r11);', {}),
    # ---- events / interrupts -------------------------------------------------------------
    'WAITEU': ('waiteu', 'WAITEU', {}),
    'WAITET': ('waitet {1}', 'WAITET', {}),
    'WAITEF': ('waitef {1}', 'WAITEF', {}),
    'CLRE': ('clre', 'clre();', {}),
    'SETV': ('setv res[{1}], r11', 'setv({1}, r11);', {}),
    'SETEV': ('setev res[{1}], r11', 'setev({1}, r11);', {}),
    'EDU': ('edu res[{1}]', 'edu({1});', {}),
    'EEU': ('eeu res[{1}]', 'eeu({1});', {}),
    'EEF': ('eef {1}, res[{2}]', 'eef({1}, {2});', {}),
    'EET': ('eet {1}, res[{2}]', 'eet({1}, {2});', {}),
    # ---- resources: generic, ports, channels, timers, threads ------------------------------
    'GETR': ('getr {1}, {2}', '{1} = getr({2});', {}),
    'FREER': ('freer res[{1}]', 'freer({1});', {}),
    'SETC': ('setc res[{1}], {2}', 'setc({1}, {2});', {}),
    'SETCI': ('setc res[{1}], {2}', 'setc({1}, {2});', {1: 'r'}),
    'SETD': ('setd res[{1}], {2}', 'setd({1}, {2});', {}),
    'GETD': ('getd {1}, res[{2}]', '{1} = getd({2});', {}),
    'GETN': ('getn {1}, res[{2}]', '{1} = getn({2});', {}),
    'SETN': ('setn res[{1}], {2}', 'setn({1}, {2});', {}),
    'GETPS': ('get {1}, ps[{2}]', '{1} = getps({2});', {}),
    'SETPS': ('set ps[{1}], {2}', 'setps({1}, {2});', {}),
    'SETPSC': ('setpsc res[{1}], {2}', 'setpsc({1}, {2});', {}),
    'SETPT': ('setpt res[{1}], {2}', 'setpt({1}, {2});', {}),
    'CLRPT': ('clrpt res[{1}]', 'clrpt({1});', {}),
    'SETCLK': ('setclk res[{1}], {2}', 'setclk({1}, {2});', {}),
    'SETRDY': ('setrdy res[{1}], {2}', 'setrdy({1}, {2});', {}),
    'SETTW': ('settw res[{1}], {2}', 'settw({1}, {2});', {}),
    'GETTS': ('getts {1}, res[{2}]', '{1} = getts({2});', {}),
    'GETTIME': ('gettime {1}', '{1} = gettime();', {}),
    'SYNCR': ('syncr res[{1}]', 'syncr({1});', {}),
    'PEEK': ('peek {1}, res[{2}]', '{1} = peek({2});', {}),
    'ENDIN': ('endin {1}, res[{2}]', '{1} = endin({2});', {}),
    'IN': ('in {1}, res[{2}]', '{1} = in({2});', {}),
    'INSHR': ('inshr {1}, res[{2}]', '{1} = inshr({2}, {1});', {}),
    'INPW': ('inpw {1}, res[{2}], {3}', '{1} = inpw({2}, {3});', {3: 'bp'}),
    'INT': ('int {1}, res[{2}]', '{1} = int({2});', {}),
    'INCT': ('inct {1}, res[{2}]', '{1} = inct({2});', {}),
    'OUT': ('out res[{1}], {2}', 'out({1}, {2});', {}),
    'OUTSHR': ('outshr res[{1}], {2}', '{2} = outshr({1}, {2});', {}),
    'OUTPW': ('outpw res[{2}], {1}, {3}', 'outpw({2}, {1}, {3});', {}),
    'OUTPWI': ('outpw res[{2}], {1}, {3}', 'outpw({2}, {1}, {3});', {3: 'bp'}),
    'OUTT': ('outt res[{1}], {2}', 'outt({1}, {2});', {}),
    'OUTCT': ('outct res[{1}], {2}', 'outct({1}, {2});', {}),
    'OUTCTI': ('outct res[{1}], {2}', 'outct({1}, {2});', {}),
    'CHKCT': ('chkct res[{1}], {2}', 'chkct({1}, {2});', {}),
    'CHKCTI': ('chkct res[{1}], {2}', 'chkct({1}, {2});', {}),
    'TESTCT': ('testct {1}, res[{2}]', '{1} = testct({2});', {}),
    'TESTWCT': ('testwct {1}, res[{2}]', '{1} = testwct({2});', {}),
    'TESTLCL': ('testlcl {1}, res[{2}]', '{1} = testlcl({2});', {}),
    'GETST': ('getst {1}, res[{2}]', '{1} = getst({2});', {}),
    'MSYNC': ('msync res[{1}]', 'msync({1});', {}),
    'MJOIN': ('mjoin res[{1}]', 'mjoin({1});', {}),
    'SSYNC': ('ssync', 'ssync();', {}),
    'FREET': ('freet', 'freet();', {}),
    'TSTART': ('start t[{1}]', 'tstart({1});', {}),
    'TINITPC': ('init t[{2}]:pc, {1}', 'tinitpc({2}, {1});', {}),
    'TINITSP': ('init t[{2}]:sp, {1}', 'tinitsp({2}, {1});', {}),
    'TINITDP': ('init t[{2}]:dp, {1}', 'tinitdp({2}, {1});', {}),
    'TINITCP': ('init t[{2}]:cp, {1}', 'tinitcp({2}, {1});', {}),
    'TINITLR': ('init t[{2}]:lr, {1}', 'tinitlr({2}, {1});', {}),
    'TSETR': ('set t[{3}]:r{1}, {2}', 'tsetr({3}, {1}, {2});', {1: 'rn'}),
    'TSETMR': ('tsetmr r{1}, {2}', 'tsetmr({1}, {2});', {1: 'rn'}),
    # ---- debug vector access (XS3) -----------------------------------------------------------
    'DVLD': ('dvld {1}, {2}, {3}', 'dvld({1}, {2}, {3});', {}),
    'DVST': ('dvst {1}, {2}, {3}', 'dvst({1}, {2}, {3});', {}),
    # ---- vector unit (XS3) ---------------------------------------------------------------------
    'VLDR': ('vldr r11[0]', 'vR = *:32 r11;', {}),
    'VLDD': ('vldd {1}[0]', 'vD = *:32 {1};', {}),
    'VLDC': ('vldc {1}[0]', 'vC = *:32 {1};', {}),
    'VSTR': ('vstr {1}[0]', '*:32 {1} = vR; vH = vheadroom(vH, vR);', {}),
    'VSTD': ('vstd {1}[0]', '*:32 {1} = vD; vH = vheadroom(vH, vD);', {}),
    'VSTC': ('vstc r11[0]', '*:32 r11 = vC; vH = vheadroom(vH, vC);', {}),
    'VSTRPV': ('vstrpv {1}[0], {2}', 'local m:32 = *:32 {1}; *:32 {1} = vstrpv(m, vR, {2});', {}),
    'VCLRDR': ('vclrdr', 'vD = vzero(); vR = vzero();', {}),
    'VSETC': ('vsetc r11', 'vSR = (r11 >> 6) & 0x3ff; vH = vsetc_headroom(r11);', {}),
    'VGETC': ('vgetc r11', 'r11 = (vSR << 6) | lzcount(vH);', {}),
    'VLADD': ('vladd {1}[0]', 'vR = vladd(vR, *:32 {1}, vSR);', {}),
    'VLSUB': ('vlsub {1}[0]', 'vR = vlsub(vR, *:32 {1}, vSR);', {}),
    'VLMUL': ('vlmul {1}[0]', 'vR = vlmul(vR, *:32 {1}, vSR);', {}),
    'VLADDD': ('vladdd r11[0]', 'vD = vladd(vD, *:32 r11, vSR);', {}),
    'VLADSB': ('vladsb {1}[0]',
               'local m:32 = *:32 {1}; local r:32 = vladsb_r(m, vR, vSR); vD = vladsb_d(m, vR, vSR); vR = r;', {}),
    'VLASHR': ('vlashr {1}[0], {2}', 'vR = vlashr(*:32 {1}, {2}, vSR);', {}),
    'VLMACC': ('vlmacc {1}[0]',
               'local m:32 = *:32 {1}; local r:32 = vlmacc_r(vD, vR, vC, m, vSR); '
               'vD = vlmacc_d(vD, vR, vC, m, vSR); vR = r;', {}),
    'VLMACCR': ('vlmaccr {1}[0]',
                'local m:32 = *:32 {1}; local r:32 = vlmaccr_r(vD, vR, vC, m, vSR); '
                'vD = vlmaccr_d(vD, vR, vC, m, vSR); vR = r;', {}),
    'VLMACCR1': ('vlmaccr1 {1}[0]',
                 'local m:32 = *:32 {1}; local r:32 = vlmaccr1_r(vD, vR, vC, m, vSR); '
                 'vD = vlmaccr1_d(vD, vR, vC, m, vSR); vR = r;', {}),
    'VLSAT': ('vlsat {1}[0]', 'vR = vlsat(vD, vR, *:32 {1}, vSR); vD = vzero();', {}),
    'VADDDR': ('vadddr', 'local r:32 = vadddr_r(vD, vR, vSR); vD = vadddr_d(vD, vR, vSR); vR = r;', {}),
    'VCMR': ('vcmr', 'vR = vcmr(vD, vC, vSR);', {}),
    'VCMI': ('vcmi', 'vR = vcmi(vD, vC, vR, vSR);', {}),
    'VCMCR': ('vcmcr', 'vR = vcmcr(vD, vC, vSR);', {}),
    'VCMCI': ('vcmci', 'vR = vcmci(vD, vC, vR, vSR);', {}),
    'VDEPTH1': ('vdepth1', 'vR = vdepth1(vR, vSR);', {}),
    'VDEPTH8': ('vdepth8', 'vR = vdepth8(vR, vSR);', {}),
    'VDEPTH16': ('vdepth16', 'vR = vdepth16(vR, vSR);', {}),
    'VEQCR': ('veqcr r10', 'r10 = zext(vC == vR);', {}),
    'VEQDR': ('veqdr r10', 'r10 = zext(vD == vR);', {}),
    'VFTFB': ('vftfb', 'vR = vftfb(vR, vSR);', {}),
    'VFTFF': ('vftff', 'vR = vftff(vR, vSR);', {}),
    'VFTTB': ('vfttb', 'vD = vfttb(vD, vSR);', {}),
    'VFTTF': ('vfttf', 'vD = vfttf(vD, vSR);', {}),
    'VPOS': ('vpos', 'vR = vpos(vR, vSR);', {}),
    'VSIGN': ('vsign', 'vR = vsign(vR, vSR);', {}),
}

# Semantics that need format-level knowledge (stack frame ops, register jumps, waits).
SPECIAL = {
    'ENTSP': 'if ({1} == 0) goto <done>; *:4 sp = lr; sp = sp - {1} * 4; <done>',
    'DUALENTSP': 'if ({1} == 0) goto <done>; *:4 sp = lr; sp = sp - {1} * 4; <done>',
    'RETSP': 'if ({1} == 0) goto <noload>; sp = sp + {1} * 4; lr = *:4 sp; <noload> return [lr];',
    'BRU': 'local t:4 = {BASE} + {1} * {IW}; goto [t];',
    'WAITEU': 'local v:4 = waitevent(); goto [v];',
    'WAITET': 'if ({1} == 0) goto inst_next; local v:4 = waitevent(); goto [v];',
    'WAITEF': 'if ({1} != 0) goto inst_next; local v:4 = waitevent(); goto [v];',
}

SPECIAL_ZERO = {'ENTSP': '', 'DUALENTSP': '', 'RETSP': 'return [lr];'}

FMT_DEFAULT_KINDS = {
    '3r': ['r', 'r', 'r'], 'l3r': ['r', 'r', 'r'], '2rus': ['r', 'r', 'us'], 'l2rus': ['r', 'r', 'us'],
    'ru6': ['R', 'u'], 'lru6': ['R', 'u'], 'u6': ['u'], 'lu6': ['u'], 'u10': ['u'], 'lu10': ['u'],
    '2r': ['r', 'r'], 'r2r': ['r', 'r'], 'l2r': ['r', 'r'], 'lr2r': ['r', 'r'], 'rus': ['r', 'us'],
    '1r': ['r'], '0r': [], 'l0r': [], 'l4r': ['r', 'r', 'r', 'r'], 'l3rus': ['r', 'r', 'us', 'r'],
    'l4rus': ['r', 'r', 'r', 'r', 'bp'], 'l5r': ['r'] * 5, 'l6r': ['r'] * 6,
}

# where each doc operand of each format lives: (location, position)
#   location: s3/s2 (16-bit word 3-op / 2-op packing), l3/l2 (32-bit low half), h3/h2 (32-bit high half)
#   ru6 (16-bit ru6 reg), lru6 (32-bit ru6 reg), imm6/imm10 (16-bit), limm16/limm20 (32-bit), r4/hr4
FMT_LOC = {
    '3r': [('s3', 1), ('s3', 2), ('s3', 3)], '2rus': [('s3', 1), ('s3', 2), ('s3', 3)],
    'l3r': [('l3', 1), ('l3', 2), ('l3', 3)], 'l2rus': [('l3', 1), ('l3', 2), ('l3', 3)],
    'ru6': [('ru6', 0), ('imm6', 0)], 'lru6': [('lru6', 0), ('limm16', 0)],
    'u6': [('imm6', 0)], 'lu6': [('limm16', 0)], 'u10': [('imm10', 0)], 'lu10': [('limm20', 0)],
    '2r': [('s2', 1), ('s2', 2)], 'r2r': [('s2', 2), ('s2', 1)], 'rus': [('s2', 1), ('s2', 2)],
    'l2r': [('l2', 1), ('l2', 2)], 'lr2r': [('l2', 2), ('l2', 1)],
    '1r': [('r4', 0)], '0r': [], 'l0r': [],
    'l4r': [('l3', 1), ('l3', 2), ('l3', 3), ('hr4', 0)],
    'l3rus': [('l3', 1), ('l3', 2), ('l3', 3), ('hr4', 0)],
    'l4rus': [('l3', 1), ('l3', 2), ('l3', 3), ('h2', 1), ('h2', 2)],
    'l5r': [('l3', 1), ('l3', 2), ('l3', 3), ('h2', 1), ('h2', 2)],
    'l6r': [('l3', 1), ('l3', 2), ('l3', 3), ('h3', 1), ('h3', 2), ('h3', 3)],
}
LONG_FMTS = {'l3r', 'l2rus', 'lru6', 'lu6', 'lu10', 'l2r', 'lr2r', 'l0r', 'l4r', 'l3rus', 'l4rus', 'l5r',
             'l6r'}

# packed-operand field groups: prefix -> (token, c5 field lo bit, base bit offset)
PACK = {'s': ('hw', 0), 'l': ('lw', 0), 'h': ('lw', 16)}


class Gen:
    def __init__(self, variant):
        self.v = variant
        self.dual = variant != 'xs1'
        self.fields = {'hw': {}, 'lw': {}}   # name -> (lo, hi, attrs)
        self.attach = []                     # (fieldnames, reglist)
        self.tables = []                     # subtable text
        self.made = set()
        self.cons = []

    # -- fields --------------------------------------------------------------------------
    def field(self, tok, lo, hi, attrs=''):
        name = '%s_%d_%d%s' % ('s' if tok == 'hw' else 'l', hi, lo, '_' + attrs if attrs else '')
        self.fields[tok][name] = (lo, hi, 'dec' if attrs == 'd' else '')
        return name

    def regfield(self, tok, lo, hi, regs, tag):
        name = '%s_%d_%d_%s' % ('s' if tok == 'hw' else 'l', hi, lo, tag)
        if name not in self.fields[tok]:
            self.fields[tok][name] = (lo, hi, '')
            self.attach.append((name, regs))
        return name

    # -- packed operands -------------------------------------------------------------------
    # The 3-operand / 2-operand packings store the high two bits of each register number in a
    # combined base-3 field. Each instruction is expanded into one constructor per value of that
    # combined field so that every constructor has a plain (non-OR) bit pattern.
    def packed_alts(self, grp, poslist):
        """Return list of (constraints, {pos: (hi, lo_bit)}) for packing group grp (s3/l3/h3/s2/l2/h2)."""
        tok, base = PACK[grp[0]]
        c5 = self.field(tok, base + 6, base + 10)
        alts = []
        if grp[1] == '3':
            for c in range(27):
                his = {1: c % 3, 2: (c // 3) % 3, 3: c // 9}
                alts.append((['%s=%d' % (c5, c)], {p: (his[p], {1: 4, 2: 2, 3: 0}[p]) for p in poslist}))
        else:
            b5 = self.field(tok, base + 5, base + 5)
            for x in range(9):
                cv, bv = (27 + x, 0) if x < 5 else (22 + x, 1)
                his = {1: x % 3, 2: x // 3}
                alts.append((['%s=%d' % (c5, cv), '%s=%d' % (b5, bv)],
                             {p: (his[p], {1: 2, 2: 0}[p]) for p in poslist}))
        return alts

    def packed_op(self, grp, hi, lo_bit, kind):
        """(display, semantic, extra pattern operands) for one packed operand with known hi bits."""
        tok, base = PACK[grp[0]]
        lo = base + lo_bit
        if kind in ('r', 'R', 'rn'):
            rf = self.regfield(tok, lo, lo + 1, ['r%d' % (hi * 4 + i) for i in range(4)], 'g%d' % hi)
            if kind != 'rn':
                return rf, rf, [rf]
            name = '%s_rn%d_%d' % (grp[0], lo, hi)
        elif kind == 'us':
            name = '%s_us%d_%d' % (grp[0], lo, hi)
        elif kind == 'bp':
            name = '%s_bp%d_%d' % (grp[0], lo, hi)
        else:
            raise ValueError(kind)
        if name not in self.made:
            self.made.add(name)
            f = self.field(tok, lo, lo + 1)
            if kind in ('us', 'rn'):
                self.tables.append('%s: val is %s [ val = %d + %s; ] { export *[const]:4 val; }'
                                   % (name, f, hi * 4, f))
            else:
                self.tables.append('\n'.join('%s: %d is %s=%d { export %d:4; }'
                                             % (name, BITP[hi * 4 + l], f, l, BITP[hi * 4 + l])
                                             for l in range(4)))
        if kind == 'rn':
            rf = self.regfield(tok, lo, lo + 1, ['r%d' % (hi * 4 + i) for i in range(4)], 'g%d' % hi)
            return rf, name, [rf, name]
        return name, name, [name]

    def reg4(self, tok, lo, kind):
        """4-bit register field: kind r (r0-r11 only) or R (all 16)."""
        name = '%s%s4_%d' % ('s' if tok == 'hw' else 'l', kind, lo)
        if name in self.made:
            return name
        self.made.add(name)
        if kind == 'R':
            rf = self.regfield(tok, lo, lo + 3, ['r%d' % i for i in range(12)] + ['cp', 'dp', 'sp', 'lr'], 'RR')
            self.tables.append('%s: %s is %s { export %s; }' % (name, rf, rf, rf))
        else:
            f = self.field(tok, lo, lo + 3)
            rf = self.regfield(tok, lo, lo + 3, ['r%d' % i for i in range(12)] + ['cp', 'dp', 'sp', 'lr'], 'RR')
            self.tables.append('\n'.join('%s: %s is %s=%d & %s { export %s; }' % (name, rf, f, i, rf, rf)
                                         for i in range(12)))
        return name

    def imm(self, loc, kind):
        """Immediate / pc-relative operands of the u6/u10/ru6 families."""
        name = '%s_%s' % (loc, kind)
        if name in self.made:
            return name
        self.made.add(name)
        if loc == 'imm6':
            e, tokexpr = None, self.field('hw', 0, 5, 'd')
        elif loc == 'imm10':
            tokexpr = self.field('hw', 0, 9, 'd')
        elif loc == 'limm16':
            hi, lo = self.field('lw', 0, 9), self.field('lw', 16, 21)
        elif loc == 'limm20':
            hi, lo = self.field('lw', 0, 9), self.field('lw', 16, 25)
        if loc in ('imm6', 'imm10'):
            pat = tokexpr
            valexpr = tokexpr
        else:
            pat = '%s & %s' % (hi, lo)
            valexpr = '(%s << %d) | %s' % (hi, 6 if loc == 'limm16' else 10, lo)
        out = []
        if kind == 'u' and loc in ('imm6', 'imm10'):
            out.append('%s: %s is %s { export *[const]:4 %s; }' % (name, pat, pat, pat))
        elif kind == 'u':
            out.append('%s: val is %s [ val = %s; ] { export *[const]:4 val; }' % (name, pat, valexpr))
        else:
            sign = '+' if kind in ('brf', 'apf') else '-'
            exp = '*:4 tgt' if kind in ('brf', 'brb') else '*[const]:4 tgt'
            if self.dual:
                out.append('%s: tgt is %s & dual=0 [ tgt = inst_next %s (%s) * 2; ] { export %s; }'
                           % (name, pat, sign, valexpr, exp))
                out.append('%s: tgt is %s & dual=1 [ tgt = ((inst_start + 4) & 0xfffffffc) %s (%s) * 4; ] '
                           '{ export %s; }' % (name, pat, sign, valexpr, exp))
            else:
                out.append('%s: tgt is %s [ tgt = inst_next %s (%s) * 2; ] { export %s; }'
                           % (name, pat, sign, valexpr, exp))
        self.tables.append('\n'.join(out))
        return name

    def operand(self, fmt, idx, kind):
        loc, pos = FMT_LOC[fmt][idx]
        if loc == 'ru6':
            return self.reg4('hw', 6, kind)
        if loc == 'lru6':
            return self.reg4('lw', 22, kind)
        if loc == 'r4':
            return self.reg4('hw', 0, 'r')
        if loc == 'hr4':
            return self.reg4('lw', 16, 'r')
        return self.imm(loc, kind)

    # -- constraint from doc pattern ------------------------------------------------------------
    def constraints(self, fmt, bits):
        cons = []
        if fmt in LONG_FMTS:
            assert len(bits) == 2, (fmt, bits)
            words = [(bits[0], 0), (bits[1], 16)]
            tok = 'lw'
        else:
            assert len(bits) == 1, (fmt, bits)
            words = [(bits[0], 0)]
            tok = 'hw'
        for pat, off in words:
            assert len(pat) == 16, pat
            b = 15
            while b >= 0:
                ch = pat[15 - b]
                if ch in '01':
                    hi = b
                    while b >= 0 and pat[15 - b] in '01':
                        b -= 1
                    lo = b + 1
                    val = int(pat[15 - hi:15 - lo + 1], 2)
                    cons.append('%s=0x%x' % (self.field(tok, off + lo, off + hi), val))
                else:
                    b -= 1
        return cons

    # -- instructions ---------------------------------------------------------------------------
    def instr(self, name, fmt, bits):
        import itertools
        asm, sem, over = SPEC[name]
        kinds = list(FMT_DEFAULT_KINDS[fmt])
        for k, v in over.items():
            if k - 1 < len(kinds):
                kinds[k - 1] = v
        if name == 'OUTPW' and fmt == 'l2rus':
            kinds[2] = 'bp'
        if name == 'TSETMR':
            kinds[0] = 'rn'
        cons = self.constraints(fmt, bits)
        # packing groups
        groups = {}
        for i in range(len(kinds)):
            loc, pos = FMT_LOC[fmt][i]
            if loc[1:] in ('3', '2'):
                groups.setdefault(loc, []).append((i + 1, pos))
        fixed = {}
        for i, kd in enumerate(kinds):
            loc, pos = FMT_LOC[fmt][i]
            if loc[1:] not in ('3', '2'):
                o = self.operand(fmt, i, kd)
                fixed[i + 1] = (o, o, [o])
        galts = []
        for g, members in groups.items():
            alts = []
            for gcons, his in self.packed_alts(g, [p for _, p in members]):
                ops = {}
                for n, p in members:
                    hi, lo_bit = his[p]
                    ops[n] = self.packed_op(g, hi, lo_bit, kinds[n - 1])
                alts.append((gcons, ops))
            galts.append(alts)
        m = re.match(r'(\S+)\s*(.*)', asm)
        mnem, rest = m.group(1), m.group(2)
        if name in SPECIAL:
            sem = SPECIAL[name]
        for combo in itertools.product(*galts) if galts else [()]:
            ops = dict(fixed)
            ccons = list(cons)
            for gcons, gops in combo:
                ccons += gcons
                ops.update(gops)
            disp = rest
            for n in ops:
                if kinds[n - 1] == 'rn':
                    disp = disp.replace('r{%d}' % n, '{%d}' % n)
            disp = re.sub(r'(?<![{\w])([A-Za-z_]\w*)', r'"\1"', disp)
            for n, (d, _, _) in ops.items():
                disp = disp.replace('{%d}' % n, d)
            body = sem
            for n, (_, se, _) in ops.items():
                body = body.replace('{%d}' % n, se)
            pats = []
            for n in sorted(ops):
                for x in ops[n][2]:
                    if x not in pats:
                        pats.append(x)
            pattern = ' & '.join(ccons + pats)
            action = ''
            if name == 'DUALENTSP' and self.dual:
                action = ' [ dual = 1; globalset(inst_next, dual); ]'
            elif name == 'ENTSP' and self.dual:
                action = ' [ dual = 0; globalset(inst_next, dual); ]'
            if name == 'BRU':
                if not self.dual:
                    b0 = body.replace('{BASE}', 'inst_next').replace('{IW}', '2')
                    self.cons.append(':%s %s is %s { %s }' % (mnem, disp, pattern, b0))
                    continue
                # The issue-mode split lives in subtables: a top-level "bru ... & dual=N" pair is
                # not a superset of the fully specified 16-bit XS3 opcodes that share BRU's
                # opcode space (VFTFF 0x2fec, VFTTF 0x2fed), and SLEIGH then picked BRU and failed
                # on the r12/r13 register field.
                if not any(t.startswith('bru_base:') for t in self.tables):
                    self.tables.append(
                        'bru_base: tgt is dual=0 [ tgt = inst_next; ] { export *[const]:4 tgt; }\n'
                        'bru_base: tgt is dual=1 [ tgt = (inst_start + 4) & 0xfffffffc; ] { export *[const]:4 tgt; }\n'
                        'bru_iw: tgt is dual=0 [ tgt = 2; ] { export *[const]:4 tgt; }\n'
                        'bru_iw: tgt is dual=1 [ tgt = 4; ] { export *[const]:4 tgt; }')
                b = body.replace('{BASE}', 'bru_base').replace('{IW}', 'bru_iw')
                self.cons.append(':%s %s is %s & bru_base & bru_iw { %s }' % (mnem, disp, pattern, b))
                continue
            if name in SPECIAL_ZERO:
                # u == 0 needs no stack access: emit a more specific constructor instead of a
                # constant-condition branch (which leaves dead blocks in the decompiler)
                zero = 's_5_0_d=0' if 'imm6_u' in pattern else 'l_9_0=0 & l_21_16=0'
                self.cons.append(':%s %s is %s & %s%s { %s }'
                                 % (mnem, disp, pattern, zero, action, SPECIAL_ZERO[name]))
                body = re.sub(r'if \(\S+ == 0\) goto <\w+>; ', '', body)
                body = re.sub(r' ?<\w+>', '', body)
            self.cons.append(':%s %s is %s%s { %s }' % (mnem, disp, pattern, action, body))

    def build(self):
        enc = ENC[self.v]
        for name in sorted(enc):
            if name not in SPEC:
                raise SystemExit('no SPEC for %s' % name)
            for fmt, bits in enc[name]:
                self.instr(name, fmt, bits)
        return self.render()

    def render(self):
        o = []
        o.append('# xCORE %s SLEIGH specification -- GENERATED by scripts/gen_sleigh.py, do not edit.' % self.v.upper())
        o.append('@include "xcore_common.sinc"')
        o.append('define context contextreg\n  dual = (0,0)\n;')
        for tok, size in (('hw', 16), ('lw', 32)):
            o.append('define token %s (%d)' % (tok, size))
            for n, (lo, hi, attr) in sorted(self.fields[tok].items()):
                o.append('  %s = (%d,%d) %s' % (n, lo, hi, attr))
            o.append(';')
        for f, regs in self.attach:
            o.append('attach variables [ %s ] [ %s ];' % (f, ' '.join(regs)))
        o.append('')
        o.extend(self.tables)
        o.append('')
        o.extend(self.cons)
        return '\n'.join(o) + '\n'


def main():
    outdir = os.path.join(HERE, '..', 'data', 'languages')
    for v in ('xs1', 'xs2', 'xs3'):
        txt = Gen(v).build()
        with open(os.path.join(outdir, 'xcore_%s.slaspec' % v), 'w') as f:
            f.write(txt)
        print('wrote xcore_%s.slaspec (%d constructors)' % (v, txt.count('\n:')))


if __name__ == '__main__':
    main()
