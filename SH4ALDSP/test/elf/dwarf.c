/* (From aleph-void/ghidra-sh, MIT.)  DWARF / calling-convention test program for test/dwarf-check.sh (sh-elf gcc, -g -O1,
   -nostdlib).  Stack arguments, a loop, a switch, a call, float arguments (soft float on the SH4AL-DSP: R4-R7),
   a struct pointer and a delay-slot return. */
struct pt { int x; short y; char tag; };
int add3(int a, int b, int c) { return a + b * c; }
int sum(int *p, int n) { int s = 0; for (int i = 0; i < n; i++) s += p[i]; return s; }
int sw(int x) { switch (x) { case 0: return 10; case 1: return 22; case 2: return 31; case 3: return 47; case 5: return 9; default: return -1; } }
extern int ext(int);
int caller(int x) { return ext(x + 1) * 2 + add3(x, 2, 3); }
float fmuladd(float a, float b) { return a * b + 1.0f; }
int field(struct pt *p) { return p->x + p->y + p->tag; }
int many(int a, int b, int c, int d, int e, int f) { return a + b + c + d + e + f; }
int ext(int v) { return v - 7; }
void _start(void) { caller(3); for (;;); }
