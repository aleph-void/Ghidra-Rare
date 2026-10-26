/* Small double-precision math library for the i860 test programs (bare metal). Accuracy is
 * modest; the programs are only compiled and analysed, not checked numerically. Written for
 * this module (MIT). */
#define PI 3.14159265358979323846

double fabs(double x) { return x < 0 ? -x : x; }

double floor(double x)
{
	double i = (double)(long)x;
	return i > x ? i - 1.0 : i;
}

double ceil(double x)
{
	double i = (double)(long)x;
	return i < x ? i + 1.0 : i;
}

double sqrt(double x)
{
	double r = x > 1.0 ? x : 1.0;
	int i;
	if (x <= 0.0)
		return 0.0;
	for (i = 0; i < 60; i++)
		r = 0.5 * (r + x / r);
	return r;
}

static double reduce(double x)
{
	while (x > PI)
		x -= 2 * PI;
	while (x < -PI)
		x += 2 * PI;
	return x;
}

double sin(double x)
{
	double t, s;
	int n;
	x = reduce(x);
	t = s = x;
	for (n = 1; n < 12; n++) {
		t *= -x * x / ((2 * n) * (2 * n + 1));
		s += t;
	}
	return s;
}

double cos(double x) { return sin(x + PI / 2); }

double exp(double x)
{
	double t = 1.0, s = 1.0;
	int n, k = 0;
	while (x > 1.0) {
		x /= 2;
		k++;
	}
	for (n = 1; n < 20; n++) {
		t *= x / n;
		s += t;
	}
	while (k--)
		s *= s;
	return s;
}

double log(double x)
{
	double y = 0.0, z;
	int i;
	if (x <= 0.0)
		return -1e300;
	while (x > 2.0) {
		x /= 2.718281828459045;
		y += 1.0;
	}
	z = (x - 1) / (x + 1);
	for (i = 0; i < 30; i++)
		y += 2 * __builtin_powi(z, 2 * i + 1) / (2 * i + 1);
	return y;
}

double pow(double a, double b) { return exp(b * log(a)); }

double atan(double x)
{
	double s = 0, t = x;
	int n;
	if (x > 1.0)
		return PI / 2 - atan(1.0 / x);
	if (x < -1.0)
		return -PI / 2 - atan(1.0 / x);
	for (n = 0; n < 40; n++) {
		s += t / (2 * n + 1);
		t *= -x * x;
	}
	return s;
}

double acos(double x) { return PI / 2 - atan(x / sqrt(1 - x * x)); }

double cbrt(double x)
{
	double r = x;
	int i;
	if (x == 0.0)
		return 0.0;
	for (i = 0; i < 60; i++)
		r = r - (r * r * r - x) / (3 * r * r);
	return r;
}

float sqrtf(float x) { return (float)sqrt(x); }
float fabsf(float x) { return x < 0 ? -x : x; }
