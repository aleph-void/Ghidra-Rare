// Test kernels for the SASS module (original code, no NVIDIA headers or libdevice).
//
// Compiled to PTX by clang (CUDA device-only mode, -nocudainc -nocudalib) and to
// cubins by ptxas for every SM generation: test/build-cu-cubins.sh.  The point is
// instruction variety - integer/float/double arithmetic, conversions, bit
// manipulation, shared/local/global memory of every width, atomics, warp
// shuffles and votes, barriers, calls, indirect branches - not useful results.

#define __global__ __attribute__((global))
#define __device__ __attribute__((device))
#define __shared__ __attribute__((shared))
#define NOINLINE __attribute__((noinline))

typedef unsigned int u32;
typedef unsigned long long u64;
typedef long long i64;
typedef float float4v __attribute__((ext_vector_type(4)));
typedef int int2v __attribute__((ext_vector_type(2)));
typedef double double2v __attribute__((ext_vector_type(2)));

static __device__ inline u32 tid() { return __nvvm_read_ptx_sreg_tid_x(); }
static __device__ inline u32 gid() {
	return __nvvm_read_ptx_sreg_ctaid_x() * __nvvm_read_ptx_sreg_ntid_x() + __nvvm_read_ptx_sreg_tid_x();
}
static __device__ inline void sync() { __nvvm_barrier_sync(0); }

#if __CUDA_ARCH__ >= 700
#define SHFL_DOWN(v, d) __nvvm_shfl_sync_down_i32(0xffffffff, (v), (d), 31)
#define SHFL_UP(v, d) __nvvm_shfl_sync_up_i32(0xffffffff, (v), (d), 0)
#define SHFL_XOR(v, d) __nvvm_shfl_sync_bfly_i32(0xffffffff, (v), (d), 31)
#define SHFL_IDX(v, d) __nvvm_shfl_sync_idx_i32(0xffffffff, (v), (d), 31)
#define SHFL_DOWNF(v, d) __nvvm_shfl_sync_down_f32(0xffffffff, (v), (d), 31)
#define BALLOT(p) __nvvm_vote_ballot_sync(0xffffffff, (p))
#define ANY(p) __nvvm_vote_any_sync(0xffffffff, (p))
#define ALL(p) __nvvm_vote_all_sync(0xffffffff, (p))
#else
#define SHFL_DOWN(v, d) __nvvm_shfl_down_i32((v), (d), 31)
#define SHFL_UP(v, d) __nvvm_shfl_up_i32((v), (d), 0)
#define SHFL_XOR(v, d) __nvvm_shfl_bfly_i32((v), (d), 31)
#define SHFL_IDX(v, d) __nvvm_shfl_idx_i32((v), (d), 31)
#define SHFL_DOWNF(v, d) __nvvm_shfl_down_f32((v), (d), 31)
#define BALLOT(p) __nvvm_vote_ballot(p)
#define ANY(p) __nvvm_vote_any(p)
#define ALL(p) __nvvm_vote_all(p)
#endif

// ---------------------------------------------------------------- integers
__global__ void k_int32(int *o, const int *a, const int *b, int n, int s) {
	u32 i = gid();
	if (i >= (u32)n) return;
	int x = a[i], y = b[i] | 1;
	u32 ux = (u32)x, uy = (u32)y;
	int r = x + y * 3 - (x >> 2);
	r ^= x * y + s;
	r += x / y + x % y;
	r += (int)(ux / uy) + (int)(ux % uy);
	r += (int)(ux / 7u) + x / -13 + x % 10;
	r += __builtin_popcount(ux) + __builtin_clz(uy) + __builtin_ctz(ux | 0x80000000u);
	r += (int)__builtin_bitreverse32(ux) + __nvvm_mulhi_i(x, y) + (int)__nvvm_mulhi_ui(ux, uy);
	r += __nvvm_mul24_i(x, y) + (x < y ? x : y) + (ux > uy ? (int)ux : (int)uy);
	r += x < 0 ? -x : x;
	r += (int)((ux << (s & 31)) | (ux >> ((32 - s) & 31)));
	r += (int)((ux >> 5) & 0x3ff) + (int)(((u32)x << 7) >> 20) + ((x << 3) >> 11);
	r += (int)__nvvm_prmt(ux, uy, 0x3210 + s) + (int)__nvvm_sad_ui(ux, uy, 5u);
	r += (x & 0xff00ff) | (y & ~0xf0f0);
	r += (int)(char)x + (int)(short)y + (int)(unsigned char)(x >> 8) + (int)(unsigned short)(y >> 3);
	o[i] = r;
}

__global__ void k_int64(i64 *o, const i64 *a, const u64 *b, int n) {
	u32 i = gid();
	if (i >= (u32)n) return;
	i64 x = a[i];
	u64 y = b[i] | 1;
	i64 r = x + (i64)y * 5 - (x >> 7);
	r ^= (i64)(y << 13) + (i64)(y >> 29) + (x << 33) + (x >> 40);
	r += x / (i64)y + x % 1000003 + (i64)(y / 12345u) + (i64)(y % (u64)(x | 3));
	r += (i64)__builtin_popcountll(y) + __builtin_clzll(y) + (i64)__builtin_bitreverse64(y);
	r += __nvvm_mulhi_ll(x, (i64)y) + (i64)__nvvm_mulhi_ull((u64)x, y);
	r += x < (i64)y ? x : (i64)y;
	r += (i64)(int)x * (i64)(int)(y >> 32);
	r += (i64)((u64)(u32)x * (u64)(u32)y);
	o[i] = r;
}

// ---------------------------------------------------------------- floats
__global__ void k_float(float *o, const float *a, const float *b, int n, float k) {
	u32 i = gid();
	if (i >= (u32)n) return;
	float x = a[i], y = b[i];
	float r = x * y + k;
	r += __builtin_fmaf(x, y, -k) - x / y;
	r += __nvvm_sqrt_rn_f(__builtin_fabsf(x)) + __nvvm_rsqrt_approx_f(y * y + 1.0f);
	r += __nvvm_ex2_approx_f(x) + __nvvm_lg2_approx_f(__builtin_fabsf(y) + 1.0f);
	r += __nvvm_sin_approx_f(x) * __nvvm_cos_approx_f(y);
	r += __nvvm_rcp_rn_f(y + 3.0f) + __nvvm_div_approx_f(x, y + 2.0f);
	r += __nvvm_fmin_f(x, y) + __nvvm_fmax_f(x, k) + __nvvm_saturate_f(x);
	r += __builtin_copysignf(x, y) + __nvvm_floor_f(x) + __nvvm_ceil_f(y) + __nvvm_trunc_f(x) + __nvvm_round_f(y);
	r += __nvvm_add_rz_f(x, y) + __nvvm_mul_rm_f(x, y) + __nvvm_fma_rp_f(x, y, k);
	r += (x > y) ? x : (x == y ? 0.5f : -y);
	r += (float)(int)x + (float)(u32)y + (float)__nvvm_f2i_rm(x) + (float)__nvvm_f2ui_rp(y);
	r += (float)__nvvm_f2ll_rz(x) + (float)(u64)y;
	r += __builtin_isnan(x) ? 1.0f : 0.0f;
	o[i] = r * 0.25f + 1.5e-3f;
}

__global__ void k_double(double *o, const double *a, const float *b, int n, double k) {
	u32 i = gid();
	if (i >= (u32)n) return;
	double x = a[i], y = (double)b[i];
	double r = x * y + k;
	r += __builtin_fma(x, y, -k) - x / (y + 1.0);
	r += __nvvm_sqrt_rn_d(__builtin_fabs(x)) + __nvvm_rcp_rn_d(y + 2.0);
	r += __nvvm_fmin_d(x, y) + __nvvm_fmax_d(x, k);
	r += __nvvm_floor_d(x) + __nvvm_ceil_d(y) + __nvvm_trunc_d(x) + __nvvm_round_d(y);
	r += __nvvm_add_rz_d(x, y) + __nvvm_mul_rp_d(x, y) + __nvvm_fma_rm_d(x, y, k);
	r += (x < y) ? x : -y;
	r += (double)(int)x + (double)(i64)y + (double)(u64)x + (double)(u32)y;
	r += (double)__nvvm_d2i_rm(x) + (double)__nvvm_d2ll_rp(y);
	o[i] = r;
	((float *)o)[i + n] = (float)r + __nvvm_d2f_rz(x);
}

// ---------------------------------------------------------------- memory widths
struct S3 { char c; short s; int i; i64 l; float f; double d; };

__global__ void k_mem(char *c, short *s, int2v *v2, float4v *v4, double2v *d2, struct S3 *st, int n) {
	u32 i = gid();
	if (i >= (u32)n) return;
	char a = c[i];
	unsigned char ua = ((unsigned char *)c)[i + 1];
	short b = s[i];
	unsigned short ub = ((unsigned short *)s)[i + 2];
	int2v x = v2[i];
	float4v y = v4[i];
	double2v z = d2[i];
	struct S3 t = st[i];
	t.c += a; t.s += b + ub; t.i += x.x + x.y + ua; t.l += t.i; t.f += y.x * y.w; t.d += z.x + z.y;
	st[i + n] = t;
	c[i + n] = (char)(a + ua);
	s[i + n] = (short)(b * 3);
	v2[i + n] = x + (int2v){1, 2};
	v4[i + n] = y * 2.0f;
	d2[i + n] = z * 0.5;
	int q = __nvvm_ldg_i((const int *)c + i);
	float qf = __nvvm_ldg_f((const float *)s + i);
	((volatile int *)v2)[i] = q + (int)qf;
}

// ---------------------------------------------------------------- shared memory, barriers, reductions
__global__ void k_shared(float *o, const float *a, int n) {
	__shared__ float sh[256];
	__shared__ int shi[256];
	__shared__ double shd[128];
	u32 t = tid(), i = gid();
	float v = i < (u32)n ? a[i] : 0.0f;
	sh[t] = v;
	shi[t] = (int)v;
	if (t < 128) shd[t] = (double)v;
	sync();
	for (u32 s = 128; s > 32; s >>= 1) {
		if (t < s) { sh[t] += sh[t + s]; shi[t] ^= shi[t + s]; }
		sync();
	}
	if (t < 32) {
		float w = sh[t] + sh[t + 32];
		for (int d = 16; d > 0; d >>= 1) w += SHFL_DOWNF(w, d);
		int iw = shi[t];
		iw += SHFL_XOR(iw, 1) + SHFL_UP(iw, 2) + SHFL_IDX(iw, t ^ 5) + SHFL_DOWN(iw, 3);
		u32 bal = BALLOT(w > 0.0f);
		if (ANY(iw < 0)) iw++;
		if (ALL(iw > 0)) iw--;
		if (t == 0) { o[__nvvm_read_ptx_sreg_ctaid_x()] = w + (float)shd[5] + (float)(iw + __builtin_popcount(bal)); }
	}
}

// ---------------------------------------------------------------- atomics, fences
__global__ void k_atomic(int *ci, u32 *cu, u64 *cl, float *cf, int n) {
	__shared__ int sc[64];
	__shared__ u32 su[64];
	u32 t = tid(), i = gid();
	if (t < 64) { sc[t] = 0; su[t] = 0; }
	sync();
	int v = (int)i;
	int old = __nvvm_atom_add_gen_i(ci, v);
	old += __nvvm_atom_max_gen_i(ci + 1, v);
	old += __nvvm_atom_min_gen_i(ci + 2, -v);
	old += (int)__nvvm_atom_max_gen_ui(cu, i);
	old += (int)__nvvm_atom_inc_gen_ui(cu + 1, 100u);
	old += (int)__nvvm_atom_dec_gen_ui(cu + 2, 100u);
	old += __nvvm_atom_xchg_gen_i(ci + 3, v);
	old += __nvvm_atom_cas_gen_i(ci + 4, v, v + 1);
	old += __nvvm_atom_and_gen_i(ci + 5, v) + __nvvm_atom_or_gen_i(ci + 6, v) + __nvvm_atom_xor_gen_i(ci + 7, v);
	u64 ol = __nvvm_atom_add_gen_ll((i64 *)cl, (i64)i) + (u64)__nvvm_atom_cas_gen_ll((i64 *)cl + 1, (i64)i, 7);
	ol += (u64)__nvvm_atom_max_gen_ll((i64 *)cl + 2, (i64)v);
	float of = __nvvm_atom_add_gen_f(cf, (float)v);
	__atomic_fetch_add(&sc[t & 63], v, __ATOMIC_RELAXED);
	__atomic_fetch_max(&su[t & 63], i, __ATOMIC_RELAXED);
	int cs = __atomic_exchange_n(&sc[(t + 1) & 63], v, __ATOMIC_RELAXED);
	__nvvm_membar_gl();
	__nvvm_membar_cta();
	__nvvm_membar_sys();
	sync();
	if (i < (u32)n) {
		ci[i + 8] = old + sc[t & 63] + cs + (int)su[t & 63];
		cl[i + 8] = ol;
		cf[i + 8] = of;
	}
}

// ---------------------------------------------------------------- control flow
static NOINLINE __device__ int collatz(u32 x) {
	int steps = 0;
	while (x != 1 && steps < 1000) {
		x = (x & 1) ? 3 * x + 1 : x >> 1;
		steps++;
	}
	return steps;
}

static NOINLINE __device__ u32 fib(u32 n) { return n < 2 ? n : fib(n - 1) + fib(n - 2); }

static NOINLINE __device__ float poly(float x, const float *c, int k) {
	float r = 0.0f;
	for (int j = k - 1; j >= 0; j--) r = r * x + c[j];
	return r;
}

__global__ void k_flow(int *o, const int *a, const float *c, int n, int mode) {
	u32 i = gid();
	if (i >= (u32)n) return;
	int x = a[i], r;
	switch ((x + mode) & 7) {
	case 0: r = x * 3; break;
	case 1: r = x ^ 0x5a5a; break;
	case 2: r = collatz((u32)x); break;
	case 3: r = (int)fib((u32)x & 15); break;
	case 4: r = (int)poly((float)x, c, mode & 7); break;
	case 5: r = x - mode; break;
	case 6: r = x << 3; break;
	default: r = -x; break;
	}
	int loc[16];
	for (int j = 0; j < 16; j++) loc[j] = x * j + r;
	r += loc[(x + mode) & 15] + loc[(u32)r % 16u];
	if (__nvvm_read_ptx_sreg_laneid() == 3) r += (int)__nvvm_read_ptx_sreg_clock();
	r += (int)__nvvm_read_ptx_sreg_warpid() + (int)__nvvm_read_ptx_sreg_nctaid_x() + (int)__nvvm_read_ptx_sreg_ctaid_y();
	o[i] = r;
}

// ---------------------------------------------------------------- indirect calls
typedef int (*op_t)(int, int);
static NOINLINE __device__ int op_add(int a, int b) { return a + b; }
static NOINLINE __device__ int op_mul(int a, int b) { return a * b; }
static NOINLINE __device__ int op_sub(int a, int b) { return a - b; }
static NOINLINE __device__ int op_div(int a, int b) { return a / (b | 1); }

__global__ void k_indirect(int *o, const int *a, int n) {
	op_t ops[4] = {op_add, op_mul, op_sub, op_div};
	u32 i = gid();
	if (i >= (u32)n) return;
	int x = a[i];
	o[i] = ops[x & 3](x, (int)i) + ops[(x >> 2) & 3](x, 7);
}

// ---------------------------------------------------------------- conversions
__global__ void k_cvt(float *of, double *od, int *oi, i64 *ol, const float *a, const double *b, int n) {
	u32 i = gid();
	if (i >= (u32)n) return;
	float x = a[i];
	double y = b[i];
	of[i] = (float)y + (float)(i64)x + __nvvm_d2f_rn(y) + __nvvm_d2f_rp(y) + __nvvm_d2f_rm(y) +
		__nvvm_i2f_rz((int)i) + __nvvm_ui2f_rp(i) + __nvvm_ll2f_rm((i64)y) + __nvvm_ull2f_rz((u64)x);
	od[i] = (double)x + __nvvm_ll2d_rp((i64)x) + __nvvm_ull2d_rm((u64)y) + __nvvm_i2d_rn((int)i) + __nvvm_ui2d_rn(i);
	oi[i] = __nvvm_f2i_rn(x) + __nvvm_f2i_rz(x) + __nvvm_f2i_rp(x) + (int)__nvvm_f2ui_rm(x) +
		__nvvm_d2i_rn(y) + __nvvm_d2i_rz(y) + (int)__nvvm_d2ui_rp(y) + __builtin_bit_cast(int, x) +
		__nvvm_d2i_hi(y) + __nvvm_d2i_lo(y);
	ol[i] = __nvvm_f2ll_rn(x) + __nvvm_f2ll_rp(x) + (i64)__nvvm_f2ull_rm(x) + __nvvm_d2ll_rz(y) +
		(i64)__nvvm_d2ull_rn(y) + __builtin_bit_cast(i64, y);
}

// ---------------------------------------------------------------- half / bfloat16
#if __CUDA_ARCH__ >= 530
__global__ void k_half(_Float16 *h, float *f, int n, float k) {
	u32 i = gid();
	if (i >= (u32)n) return;
	_Float16 a = h[i], b = h[i + n];
	_Float16 r = a * b + (_Float16)k;
	r = r - a / (b + (_Float16)1.0f);
	r = r > a ? r : a;
	f[i] = (float)r + (float)(a < b) + (float)(int)a;
	h[i + 2 * n] = (_Float16)f[i + n] + (_Float16)(int)i + (_Float16)(double)f[i];
}
#endif
#if __CUDA_ARCH__ >= 800
__global__ void k_bf16(__bf16 *h, float *f, double *d, int n) {
	u32 i = gid();
	if (i >= (u32)n) return;
	__bf16 a = h[i], b = h[i + n];
	float x = (float)a * (float)b + (float)h[i + 2 * n];
	h[i + 3 * n] = (__bf16)x;
	h[i + 4 * n] = (__bf16)d[i];
	h[i + 5 * n] = (__bf16)(int)i;
	f[i] = x + (float)(__bf16)f[i + n];
}
#endif
