/*
 * Pure C11 transliteration of double-conversion (v3.4.0) double-only paths,
 * plus the JS-specific wrapper logic from ant's original src/numbers.cc.
 *
 * This is a mechanical port: constants, tables and control flow are kept
 * verbatim relative to the vendored C++ sources in
 * vendor/double-conversion-3.4.0/double-conversion/*. Float(single)-only
 * paths have been dropped as instructed.
 */

#include "numbers.h"

#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>
#include <assert.h>
#include <limits.h>

#define DC_ASSERT(x) assert(x)
#define DC_UNREACHABLE() abort()
#define DC_ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define UINT64_2C(a, b) ((((uint64_t)(a)) << 32) + 0x##b##u)

#define DC_MIN(a, b) ((a) < (b) ? (a) : (b))
#define DC_MAX(a, b) ((a) > (b) ? (a) : (b))

/* ============================================================
 * utils.h: StringBuilder
 * ============================================================ */

typedef struct {
  char *buffer;
  int size;
  int position;
} StringBuilder;

static void sb_init(StringBuilder *sb, char *buffer, int buffer_size) {
  sb->buffer = buffer;
  sb->size = buffer_size;
  sb->position = 0;
}

static int sb_is_finalized(const StringBuilder *sb) { return sb->position < 0; }

static int sb_position(const StringBuilder *sb) {
  DC_ASSERT(!sb_is_finalized(sb));
  return sb->position;
}

static void sb_add_character(StringBuilder *sb, char c) {
  DC_ASSERT(c != '\0');
  DC_ASSERT(!sb_is_finalized(sb) && sb->position < sb->size);
  sb->buffer[sb->position++] = c;
}

static void sb_add_substring(StringBuilder *sb, const char *s, int n) {
  DC_ASSERT(!sb_is_finalized(sb) && sb->position + n < sb->size);
  if (n > 0) memmove(&sb->buffer[sb->position], s, (size_t)n);
  sb->position += n;
}

static void sb_add_string(StringBuilder *sb, const char *s) {
  sb_add_substring(sb, s, (int)strlen(s));
}

static void sb_add_padding(StringBuilder *sb, char c, int count) {
  for (int i = 0; i < count; i++) sb_add_character(sb, c);
}

static char *sb_finalize(StringBuilder *sb) {
  DC_ASSERT(!sb_is_finalized(sb) && sb->position < sb->size);
  sb->buffer[sb->position] = '\0';
  sb->position = -1;
  return sb->buffer;
}

/* ============================================================
 * diy-fp.h
 * ============================================================ */

typedef struct {
  uint64_t f;
  int32_t e;
} DiyFp;

#define DIYFP_SIGNIFICAND_SIZE 64

static DiyFp diyfp_make(uint64_t f, int32_t e) {
  DiyFp r; r.f = f; r.e = e; return r;
}

static void diyfp_subtract(DiyFp *a, const DiyFp *other) {
  DC_ASSERT(a->e == other->e);
  DC_ASSERT(a->f >= other->f);
  a->f -= other->f;
}

static DiyFp diyfp_minus(DiyFp a, DiyFp b) {
  DiyFp result = a;
  diyfp_subtract(&result, &b);
  return result;
}

static void diyfp_multiply(DiyFp *a, const DiyFp *other) {
  const uint64_t kM32 = 0xFFFFFFFFU;
  const uint64_t aa = a->f >> 32;
  const uint64_t bb = a->f & kM32;
  const uint64_t c = other->f >> 32;
  const uint64_t d = other->f & kM32;
  const uint64_t ac = aa * c;
  const uint64_t bc = bb * c;
  const uint64_t ad = aa * d;
  const uint64_t bd = bb * d;
  const uint64_t tmp = (bd >> 32) + (ad & kM32) + (bc & kM32) + (1U << 31);
  a->e += other->e + 64;
  a->f = ac + (ad >> 32) + (bc >> 32) + (tmp >> 32);
}

static DiyFp diyfp_times(DiyFp a, DiyFp b) {
  DiyFp result = a;
  diyfp_multiply(&result, &b);
  return result;
}

static void diyfp_normalize(DiyFp *a) {
  DC_ASSERT(a->f != 0);
  uint64_t significand = a->f;
  int32_t exponent = a->e;
  const uint64_t k10MSBits = UINT64_2C(0xFFC00000, 00000000);
  while ((significand & k10MSBits) == 0) {
    significand <<= 10;
    exponent -= 10;
  }
  const uint64_t kUint64MSB = UINT64_2C(0x80000000, 00000000);
  while ((significand & kUint64MSB) == 0) {
    significand <<= 1;
    exponent--;
  }
  a->f = significand;
  a->e = exponent;
}

static DiyFp diyfp_normalize_new(DiyFp a) {
  DiyFp result = a;
  diyfp_normalize(&result);
  return result;
}

/* ============================================================
 * ieee.h: Double (bit-level helpers), double-only
 * ============================================================ */

#define DBL_SIGN_MASK        UINT64_2C(0x80000000, 00000000)
#define DBL_EXPONENT_MASK    UINT64_2C(0x7FF00000, 00000000)
#define DBL_SIGNIFICAND_MASK UINT64_2C(0x000FFFFF, FFFFFFFF)
#define DBL_HIDDEN_BIT       UINT64_2C(0x00100000, 00000000)
#define DBL_QUIET_NAN_BIT    UINT64_2C(0x00080000, 00000000)
#define DBL_PHYSICAL_SIGNIFICAND_SIZE 52
#define DBL_SIGNIFICAND_SIZE 53
#define DBL_EXPONENT_BIAS (0x3FF + DBL_PHYSICAL_SIGNIFICAND_SIZE)
#define DBL_MAX_EXPONENT (0x7FF - DBL_EXPONENT_BIAS)
#define DBL_DENORMAL_EXPONENT (-DBL_EXPONENT_BIAS + 1)
#define DBL_INFINITY_BITS UINT64_2C(0x7FF00000, 00000000)
#define DBL_NAN_BITS UINT64_2C(0x7FF80000, 00000000)

static uint64_t double_to_uint64(double d) {
  uint64_t u;
  memcpy(&u, &d, sizeof(u));
  return u;
}

static double uint64_to_double(uint64_t d) {
  double v;
  memcpy(&v, &d, sizeof(v));
  return v;
}

static int dbl_sign(uint64_t d64) {
  return (d64 & DBL_SIGN_MASK) == 0 ? 1 : -1;
}

static int dbl_is_denormal(uint64_t d64) {
  return (d64 & DBL_EXPONENT_MASK) == 0;
}

static int dbl_exponent(uint64_t d64) {
  if (dbl_is_denormal(d64)) return DBL_DENORMAL_EXPONENT;
  int biased_e = (int)((d64 & DBL_EXPONENT_MASK) >> DBL_PHYSICAL_SIGNIFICAND_SIZE);
  return biased_e - DBL_EXPONENT_BIAS;
}

static uint64_t dbl_significand(uint64_t d64) {
  uint64_t significand = d64 & DBL_SIGNIFICAND_MASK;
  if (!dbl_is_denormal(d64)) return significand + DBL_HIDDEN_BIT;
  return significand;
}

static int dbl_is_special(uint64_t d64) {
  return (d64 & DBL_EXPONENT_MASK) == DBL_EXPONENT_MASK;
}

static int dbl_is_nan(uint64_t d64) {
  return (d64 & DBL_EXPONENT_MASK) == DBL_EXPONENT_MASK &&
         (d64 & DBL_SIGNIFICAND_MASK) != 0;
}

static int dbl_is_infinite(uint64_t d64) {
  return (d64 & DBL_EXPONENT_MASK) == DBL_EXPONENT_MASK &&
         (d64 & DBL_SIGNIFICAND_MASK) == 0;
}

static double dbl_value(uint64_t d64) { return uint64_to_double(d64); }

static double dbl_infinity(void) { return uint64_to_double(DBL_INFINITY_BITS); }
static double dbl_nan(void) { return uint64_to_double(DBL_NAN_BITS); }

static DiyFp dbl_as_diy_fp(uint64_t d64) {
  DC_ASSERT(dbl_sign(d64) > 0);
  DC_ASSERT(!dbl_is_special(d64));
  return diyfp_make(dbl_significand(d64), dbl_exponent(d64));
}

static DiyFp dbl_as_normalized_diy_fp(uint64_t d64) {
  DC_ASSERT(dbl_value(d64) > 0.0);
  uint64_t f = dbl_significand(d64);
  int e = dbl_exponent(d64);
  while ((f & DBL_HIDDEN_BIT) == 0) {
    f <<= 1;
    e--;
  }
  f <<= DIYFP_SIGNIFICAND_SIZE - DBL_SIGNIFICAND_SIZE;
  e -= DIYFP_SIGNIFICAND_SIZE - DBL_SIGNIFICAND_SIZE;
  return diyfp_make(f, e);
}

static DiyFp dbl_upper_boundary(uint64_t d64) {
  DC_ASSERT(dbl_sign(d64) > 0);
  return diyfp_make(dbl_significand(d64) * 2 + 1, dbl_exponent(d64) - 1);
}

static int dbl_lower_boundary_is_closer(uint64_t d64) {
  int physical_significand_is_zero = ((d64 & DBL_SIGNIFICAND_MASK) == 0);
  return physical_significand_is_zero && (dbl_exponent(d64) != DBL_DENORMAL_EXPONENT);
}

static void dbl_normalized_boundaries(uint64_t d64, DiyFp *out_m_minus, DiyFp *out_m_plus) {
  DC_ASSERT(dbl_value(d64) > 0.0);
  DiyFp v = dbl_as_diy_fp(d64);
  DiyFp m_plus = diyfp_normalize_new(diyfp_make((v.f << 1) + 1, v.e - 1));
  DiyFp m_minus;
  if (dbl_lower_boundary_is_closer(d64)) {
    m_minus = diyfp_make((v.f << 2) - 1, v.e - 2);
  } else {
    m_minus = diyfp_make((v.f << 1) - 1, v.e - 1);
  }
  m_minus.f = m_minus.f << (m_minus.e - m_plus.e);
  m_minus.e = m_plus.e;
  *out_m_plus = m_plus;
  *out_m_minus = m_minus;
}

static double dbl_next_double(uint64_t d64) {
  if (d64 == DBL_INFINITY_BITS) return dbl_value(DBL_INFINITY_BITS);
  if (dbl_sign(d64) < 0 && dbl_significand(d64) == 0) return 0.0;
  if (dbl_sign(d64) < 0) return dbl_value(d64 - 1);
  return dbl_value(d64 + 1);
}

static double dbl_previous_double(uint64_t d64) {
  if (d64 == (DBL_INFINITY_BITS | DBL_SIGN_MASK)) return -dbl_infinity();
  if (dbl_sign(d64) < 0) return dbl_value(d64 + 1);
  if (dbl_significand(d64) == 0) return -0.0;
  return dbl_value(d64 - 1);
}

static int dbl_significand_size_for_order_of_magnitude(int order) {
  if (order >= (DBL_DENORMAL_EXPONENT + DBL_SIGNIFICAND_SIZE)) return DBL_SIGNIFICAND_SIZE;
  if (order <= DBL_DENORMAL_EXPONENT) return 0;
  return order - DBL_DENORMAL_EXPONENT;
}

/* ============================================================
 * cached-powers.h / .cc
 * ============================================================ */

typedef struct {
  uint64_t significand;
  int16_t binary_exponent;
  int16_t decimal_exponent;
} CachedPower;

static const CachedPower kCachedPowers[] = {
  {UINT64_2C(0xfa8fd5a0, 081c0288), -1220, -348},
  {UINT64_2C(0xbaaee17f, a23ebf76), -1193, -340},
  {UINT64_2C(0x8b16fb20, 3055ac76), -1166, -332},
  {UINT64_2C(0xcf42894a, 5dce35ea), -1140, -324},
  {UINT64_2C(0x9a6bb0aa, 55653b2d), -1113, -316},
  {UINT64_2C(0xe61acf03, 3d1a45df), -1087, -308},
  {UINT64_2C(0xab70fe17, c79ac6ca), -1060, -300},
  {UINT64_2C(0xff77b1fc, bebcdc4f), -1034, -292},
  {UINT64_2C(0xbe5691ef, 416bd60c), -1007, -284},
  {UINT64_2C(0x8dd01fad, 907ffc3c), -980, -276},
  {UINT64_2C(0xd3515c28, 31559a83), -954, -268},
  {UINT64_2C(0x9d71ac8f, ada6c9b5), -927, -260},
  {UINT64_2C(0xea9c2277, 23ee8bcb), -901, -252},
  {UINT64_2C(0xaecc4991, 4078536d), -874, -244},
  {UINT64_2C(0x823c1279, 5db6ce57), -847, -236},
  {UINT64_2C(0xc2109436, 4dfb5637), -821, -228},
  {UINT64_2C(0x9096ea6f, 3848984f), -794, -220},
  {UINT64_2C(0xd77485cb, 25823ac7), -768, -212},
  {UINT64_2C(0xa086cfcd, 97bf97f4), -741, -204},
  {UINT64_2C(0xef340a98, 172aace5), -715, -196},
  {UINT64_2C(0xb23867fb, 2a35b28e), -688, -188},
  {UINT64_2C(0x84c8d4df, d2c63f3b), -661, -180},
  {UINT64_2C(0xc5dd4427, 1ad3cdba), -635, -172},
  {UINT64_2C(0x936b9fce, bb25c996), -608, -164},
  {UINT64_2C(0xdbac6c24, 7d62a584), -582, -156},
  {UINT64_2C(0xa3ab6658, 0d5fdaf6), -555, -148},
  {UINT64_2C(0xf3e2f893, dec3f126), -529, -140},
  {UINT64_2C(0xb5b5ada8, aaff80b8), -502, -132},
  {UINT64_2C(0x87625f05, 6c7c4a8b), -475, -124},
  {UINT64_2C(0xc9bcff60, 34c13053), -449, -116},
  {UINT64_2C(0x964e858c, 91ba2655), -422, -108},
  {UINT64_2C(0xdff97724, 70297ebd), -396, -100},
  {UINT64_2C(0xa6dfbd9f, b8e5b88f), -369, -92},
  {UINT64_2C(0xf8a95fcf, 88747d94), -343, -84},
  {UINT64_2C(0xb9447093, 8fa89bcf), -316, -76},
  {UINT64_2C(0x8a08f0f8, bf0f156b), -289, -68},
  {UINT64_2C(0xcdb02555, 653131b6), -263, -60},
  {UINT64_2C(0x993fe2c6, d07b7fac), -236, -52},
  {UINT64_2C(0xe45c10c4, 2a2b3b06), -210, -44},
  {UINT64_2C(0xaa242499, 697392d3), -183, -36},
  {UINT64_2C(0xfd87b5f2, 8300ca0e), -157, -28},
  {UINT64_2C(0xbce50864, 92111aeb), -130, -20},
  {UINT64_2C(0x8cbccc09, 6f5088cc), -103, -12},
  {UINT64_2C(0xd1b71758, e219652c), -77, -4},
  {UINT64_2C(0x9c400000, 00000000), -50, 4},
  {UINT64_2C(0xe8d4a510, 00000000), -24, 12},
  {UINT64_2C(0xad78ebc5, ac620000), 3, 20},
  {UINT64_2C(0x813f3978, f8940984), 30, 28},
  {UINT64_2C(0xc097ce7b, c90715b3), 56, 36},
  {UINT64_2C(0x8f7e32ce, 7bea5c70), 83, 44},
  {UINT64_2C(0xd5d238a4, abe98068), 109, 52},
  {UINT64_2C(0x9f4f2726, 179a2245), 136, 60},
  {UINT64_2C(0xed63a231, d4c4fb27), 162, 68},
  {UINT64_2C(0xb0de6538, 8cc8ada8), 189, 76},
  {UINT64_2C(0x83c7088e, 1aab65db), 216, 84},
  {UINT64_2C(0xc45d1df9, 42711d9a), 242, 92},
  {UINT64_2C(0x924d692c, a61be758), 269, 100},
  {UINT64_2C(0xda01ee64, 1a708dea), 295, 108},
  {UINT64_2C(0xa26da399, 9aef774a), 322, 116},
  {UINT64_2C(0xf209787b, b47d6b85), 348, 124},
  {UINT64_2C(0xb454e4a1, 79dd1877), 375, 132},
  {UINT64_2C(0x865b8692, 5b9bc5c2), 402, 140},
  {UINT64_2C(0xc83553c5, c8965d3d), 428, 148},
  {UINT64_2C(0x952ab45c, fa97a0b3), 455, 156},
  {UINT64_2C(0xde469fbd, 99a05fe3), 481, 164},
  {UINT64_2C(0xa59bc234, db398c25), 508, 172},
  {UINT64_2C(0xf6c69a72, a3989f5c), 534, 180},
  {UINT64_2C(0xb7dcbf53, 54e9bece), 561, 188},
  {UINT64_2C(0x88fcf317, f22241e2), 588, 196},
  {UINT64_2C(0xcc20ce9b, d35c78a5), 614, 204},
  {UINT64_2C(0x98165af3, 7b2153df), 641, 212},
  {UINT64_2C(0xe2a0b5dc, 971f303a), 667, 220},
  {UINT64_2C(0xa8d9d153, 5ce3b396), 694, 228},
  {UINT64_2C(0xfb9b7cd9, a4a7443c), 720, 236},
  {UINT64_2C(0xbb764c4c, a7a44410), 747, 244},
  {UINT64_2C(0x8bab8eef, b6409c1a), 774, 252},
  {UINT64_2C(0xd01fef10, a657842c), 800, 260},
  {UINT64_2C(0x9b10a4e5, e9913129), 827, 268},
  {UINT64_2C(0xe7109bfb, a19c0c9d), 853, 276},
  {UINT64_2C(0xac2820d9, 623bf429), 880, 284},
  {UINT64_2C(0x80444b5e, 7aa7cf85), 907, 292},
  {UINT64_2C(0xbf21e440, 03acdd2d), 933, 300},
  {UINT64_2C(0x8e679c2f, 5e44ff8f), 960, 308},
  {UINT64_2C(0xd433179d, 9c8cb841), 986, 316},
  {UINT64_2C(0x9e19db92, b4e31ba9), 1013, 324},
  {UINT64_2C(0xeb96bf6e, badf77d9), 1039, 332},
  {UINT64_2C(0xaf87023b, 9bf0ee6b), 1066, 340},
};

#define CACHED_POWERS_OFFSET 348
#define CACHED_POWERS_DECIMAL_EXPONENT_DISTANCE 8
#define CACHED_POWERS_MIN_DECIMAL_EXPONENT (-348)
#define CACHED_POWERS_MAX_DECIMAL_EXPONENT 340
static const double kD_1_LOG2_10 = 0.30102999566398114;

static void get_cached_power_for_binary_exponent_range(
    int min_exponent, int max_exponent, DiyFp *power, int *decimal_exponent) {
  int kQ = DIYFP_SIGNIFICAND_SIZE;
  double k = ceil((min_exponent + kQ - 1) * kD_1_LOG2_10);
  int foo = CACHED_POWERS_OFFSET;
  int index = (foo + (int)k - 1) / CACHED_POWERS_DECIMAL_EXPONENT_DISTANCE + 1;
  DC_ASSERT(0 <= index && index < (int)DC_ARRAY_SIZE(kCachedPowers));
  (void)max_exponent;
  CachedPower cached_power = kCachedPowers[index];
  *decimal_exponent = cached_power.decimal_exponent;
  *power = diyfp_make(cached_power.significand, cached_power.binary_exponent);
}

static void get_cached_power_for_decimal_exponent(
    int requested_exponent, DiyFp *power, int *found_exponent) {
  DC_ASSERT(CACHED_POWERS_MIN_DECIMAL_EXPONENT <= requested_exponent);
  DC_ASSERT(requested_exponent < CACHED_POWERS_MAX_DECIMAL_EXPONENT + CACHED_POWERS_DECIMAL_EXPONENT_DISTANCE);
  int index = (requested_exponent + CACHED_POWERS_OFFSET) / CACHED_POWERS_DECIMAL_EXPONENT_DISTANCE;
  CachedPower cached_power = kCachedPowers[index];
  *power = diyfp_make(cached_power.significand, cached_power.binary_exponent);
  *found_exponent = cached_power.decimal_exponent;
}

/* ============================================================
 * fast-dtoa.h / .cc  (Grisu3), double only
 * ============================================================ */

typedef enum { FAST_DTOA_SHORTEST, FAST_DTOA_PRECISION } FastDtoaMode;

#define FAST_DTOA_MAXIMAL_LENGTH 17
#define FD_MIN_TARGET_EXPONENT (-60)
#define FD_MAX_TARGET_EXPONENT (-32)

static int fd_round_weed(char *buffer, int length,
                          uint64_t distance_too_high_w,
                          uint64_t unsafe_interval,
                          uint64_t rest,
                          uint64_t ten_kappa,
                          uint64_t unit) {
  uint64_t small_distance = distance_too_high_w - unit;
  uint64_t big_distance = distance_too_high_w + unit;
  DC_ASSERT(rest <= unsafe_interval);
  while (rest < small_distance &&
         unsafe_interval - rest >= ten_kappa &&
         (rest + ten_kappa < small_distance ||
          small_distance - rest >= rest + ten_kappa - small_distance)) {
    buffer[length - 1]--;
    rest += ten_kappa;
  }
  if (rest < big_distance &&
      unsafe_interval - rest >= ten_kappa &&
      (rest + ten_kappa < big_distance ||
       big_distance - rest > rest + ten_kappa - big_distance)) {
    return 0;
  }
  return (2 * unit <= rest) && (rest <= unsafe_interval - 4 * unit);
}

static int fd_round_weed_counted(char *buffer, int length,
                                  uint64_t rest, uint64_t ten_kappa,
                                  uint64_t unit, int *kappa) {
  DC_ASSERT(rest < ten_kappa);
  if (unit >= ten_kappa) return 0;
  if (ten_kappa - unit <= unit) return 0;
  if ((ten_kappa - rest > rest) && (ten_kappa - 2 * rest >= 2 * unit)) {
    return 1;
  }
  if ((rest > unit) && (ten_kappa - (rest - unit) <= (rest - unit))) {
    buffer[length - 1]++;
    for (int i = length - 1; i > 0; --i) {
      if (buffer[i] != '0' + 10) break;
      buffer[i] = '0';
      buffer[i - 1]++;
    }
    if (buffer[0] == '0' + 10) {
      buffer[0] = '1';
      (*kappa) += 1;
    }
    return 1;
  }
  return 0;
}

static const unsigned int kSmallPowersOfTen[] =
    {0, 1, 10, 100, 1000, 10000, 100000, 1000000, 10000000, 100000000,
     1000000000};

static void fd_biggest_power_ten(uint32_t number, int number_bits,
                                  uint32_t *power, int *exponent_plus_one) {
  DC_ASSERT(number < (1u << (number_bits + 1)));
  int exponent_plus_one_guess = ((number_bits + 1) * 1233 >> 12);
  exponent_plus_one_guess++;
  if (number < kSmallPowersOfTen[exponent_plus_one_guess]) {
    exponent_plus_one_guess--;
  }
  *power = kSmallPowersOfTen[exponent_plus_one_guess];
  *exponent_plus_one = exponent_plus_one_guess;
}

static int fd_digit_gen(DiyFp low, DiyFp w, DiyFp high,
                         char *buffer, int *length, int *kappa) {
  DC_ASSERT(low.e == w.e && w.e == high.e);
  DC_ASSERT(low.f + 1 <= high.f - 1);
  DC_ASSERT(FD_MIN_TARGET_EXPONENT <= w.e && w.e <= FD_MAX_TARGET_EXPONENT);
  uint64_t unit = 1;
  DiyFp too_low = diyfp_make(low.f - unit, low.e);
  DiyFp too_high = diyfp_make(high.f + unit, high.e);
  DiyFp unsafe_interval = diyfp_minus(too_high, too_low);
  DiyFp one = diyfp_make((uint64_t)1 << -w.e, w.e);
  uint32_t integrals = (uint32_t)(too_high.f >> -one.e);
  uint64_t fractionals = too_high.f & (one.f - 1);
  uint32_t divisor;
  int divisor_exponent_plus_one;
  fd_biggest_power_ten(integrals, DIYFP_SIGNIFICAND_SIZE - (-one.e),
                       &divisor, &divisor_exponent_plus_one);
  *kappa = divisor_exponent_plus_one;
  *length = 0;
  while (*kappa > 0) {
    int digit = integrals / divisor;
    DC_ASSERT(digit <= 9);
    buffer[*length] = (char)('0' + digit);
    (*length)++;
    integrals %= divisor;
    (*kappa)--;
    uint64_t rest = ((uint64_t)integrals << -one.e) + fractionals;
    if (rest < unsafe_interval.f) {
      return fd_round_weed(buffer, *length, diyfp_minus(too_high, w).f,
                            unsafe_interval.f, rest,
                            (uint64_t)divisor << -one.e, unit);
    }
    divisor /= 10;
  }
  DC_ASSERT(one.e >= -60);
  DC_ASSERT(fractionals < one.f);
  DC_ASSERT(UINT64_2C(0xFFFFFFFF, FFFFFFFF) / 10 >= one.f);
  for (;;) {
    fractionals *= 10;
    unit *= 10;
    unsafe_interval.f = unsafe_interval.f * 10;
    int digit = (int)(fractionals >> -one.e);
    DC_ASSERT(digit <= 9);
    buffer[*length] = (char)('0' + digit);
    (*length)++;
    fractionals &= one.f - 1;
    (*kappa)--;
    if (fractionals < unsafe_interval.f) {
      return fd_round_weed(buffer, *length, diyfp_minus(too_high, w).f * unit,
                            unsafe_interval.f, fractionals, one.f, unit);
    }
  }
}

static int fd_digit_gen_counted(DiyFp w, int requested_digits,
                                 char *buffer, int *length, int *kappa) {
  DC_ASSERT(FD_MIN_TARGET_EXPONENT <= w.e && w.e <= FD_MAX_TARGET_EXPONENT);
  uint64_t w_error = 1;
  DiyFp one = diyfp_make((uint64_t)1 << -w.e, w.e);
  uint32_t integrals = (uint32_t)(w.f >> -one.e);
  uint64_t fractionals = w.f & (one.f - 1);
  uint32_t divisor;
  int divisor_exponent_plus_one;
  fd_biggest_power_ten(integrals, DIYFP_SIGNIFICAND_SIZE - (-one.e),
                       &divisor, &divisor_exponent_plus_one);
  *kappa = divisor_exponent_plus_one;
  *length = 0;
  while (*kappa > 0) {
    int digit = integrals / divisor;
    DC_ASSERT(digit <= 9);
    buffer[*length] = (char)('0' + digit);
    (*length)++;
    requested_digits--;
    integrals %= divisor;
    (*kappa)--;
    if (requested_digits == 0) break;
    divisor /= 10;
  }
  if (requested_digits == 0) {
    uint64_t rest = ((uint64_t)integrals << -one.e) + fractionals;
    return fd_round_weed_counted(buffer, *length, rest,
                                  (uint64_t)divisor << -one.e, w_error, kappa);
  }
  DC_ASSERT(one.e >= -60);
  DC_ASSERT(fractionals < one.f);
  DC_ASSERT(UINT64_2C(0xFFFFFFFF, FFFFFFFF) / 10 >= one.f);
  while (requested_digits > 0 && fractionals > w_error) {
    fractionals *= 10;
    w_error *= 10;
    int digit = (int)(fractionals >> -one.e);
    DC_ASSERT(digit <= 9);
    buffer[*length] = (char)('0' + digit);
    (*length)++;
    requested_digits--;
    fractionals &= one.f - 1;
    (*kappa)--;
  }
  if (requested_digits != 0) return 0;
  return fd_round_weed_counted(buffer, *length, fractionals, one.f, w_error, kappa);
}

static int fd_grisu3(double v, FastDtoaMode mode,
                      char *buffer, int *length, int *decimal_exponent) {
  uint64_t v64 = double_to_uint64(v);
  DiyFp w = dbl_as_normalized_diy_fp(v64);
  DiyFp boundary_minus, boundary_plus;
  DC_ASSERT(mode == FAST_DTOA_SHORTEST);
  dbl_normalized_boundaries(v64, &boundary_minus, &boundary_plus);
  DiyFp ten_mk;
  int mk;
  int ten_mk_minimal_binary_exponent =
      FD_MIN_TARGET_EXPONENT - (w.e + DIYFP_SIGNIFICAND_SIZE);
  int ten_mk_maximal_binary_exponent =
      FD_MAX_TARGET_EXPONENT - (w.e + DIYFP_SIGNIFICAND_SIZE);
  get_cached_power_for_binary_exponent_range(
      ten_mk_minimal_binary_exponent, ten_mk_maximal_binary_exponent,
      &ten_mk, &mk);
  DiyFp scaled_w = diyfp_times(w, ten_mk);
  DiyFp scaled_boundary_minus = diyfp_times(boundary_minus, ten_mk);
  DiyFp scaled_boundary_plus = diyfp_times(boundary_plus, ten_mk);
  int kappa;
  int result = fd_digit_gen(scaled_boundary_minus, scaled_w, scaled_boundary_plus,
                             buffer, length, &kappa);
  *decimal_exponent = -mk + kappa;
  return result;
}

static int fd_grisu3_counted(double v, int requested_digits,
                              char *buffer, int *length, int *decimal_exponent) {
  uint64_t v64 = double_to_uint64(v);
  DiyFp w = dbl_as_normalized_diy_fp(v64);
  DiyFp ten_mk;
  int mk;
  int ten_mk_minimal_binary_exponent =
      FD_MIN_TARGET_EXPONENT - (w.e + DIYFP_SIGNIFICAND_SIZE);
  int ten_mk_maximal_binary_exponent =
      FD_MAX_TARGET_EXPONENT - (w.e + DIYFP_SIGNIFICAND_SIZE);
  get_cached_power_for_binary_exponent_range(
      ten_mk_minimal_binary_exponent, ten_mk_maximal_binary_exponent,
      &ten_mk, &mk);
  DiyFp scaled_w = diyfp_times(w, ten_mk);
  int kappa;
  int result = fd_digit_gen_counted(scaled_w, requested_digits, buffer, length, &kappa);
  *decimal_exponent = -mk + kappa;
  return result;
}

static int fast_dtoa(double v, FastDtoaMode mode, int requested_digits,
                      char *buffer, int *length, int *decimal_point) {
  DC_ASSERT(v > 0);
  DC_ASSERT(!dbl_is_special(double_to_uint64(v)));
  int result = 0;
  int decimal_exponent = 0;
  switch (mode) {
    case FAST_DTOA_SHORTEST:
      result = fd_grisu3(v, mode, buffer, length, &decimal_exponent);
      break;
    case FAST_DTOA_PRECISION:
      result = fd_grisu3_counted(v, requested_digits, buffer, length, &decimal_exponent);
      break;
    default:
      DC_UNREACHABLE();
  }
  if (result) {
    *decimal_point = *length + decimal_exponent;
    buffer[*length] = '\0';
  }
  return result;
}

/* ============================================================
 * fixed-dtoa.h / .cc
 * ============================================================ */

typedef struct {
  uint64_t high_bits;
  uint64_t low_bits;
} UInt128;

#define UINT128_MASK32 0xFFFFFFFFu

static UInt128 uint128_make(uint64_t high, uint64_t low) {
  UInt128 r; r.high_bits = high; r.low_bits = low; return r;
}

static void uint128_multiply(UInt128 *u, uint32_t multiplicand) {
  uint64_t accumulator;
  accumulator = (u->low_bits & UINT128_MASK32) * multiplicand;
  uint32_t part = (uint32_t)(accumulator & UINT128_MASK32);
  accumulator >>= 32;
  accumulator = accumulator + (u->low_bits >> 32) * multiplicand;
  u->low_bits = (accumulator << 32) + part;
  accumulator >>= 32;
  accumulator = accumulator + (u->high_bits & UINT128_MASK32) * multiplicand;
  part = (uint32_t)(accumulator & UINT128_MASK32);
  accumulator >>= 32;
  accumulator = accumulator + (u->high_bits >> 32) * multiplicand;
  u->high_bits = (accumulator << 32) + part;
  DC_ASSERT((accumulator >> 32) == 0);
}

static void uint128_shift(UInt128 *u, int shift_amount) {
  DC_ASSERT(-64 <= shift_amount && shift_amount <= 64);
  if (shift_amount == 0) {
    return;
  } else if (shift_amount == -64) {
    u->high_bits = u->low_bits;
    u->low_bits = 0;
  } else if (shift_amount == 64) {
    u->low_bits = u->high_bits;
    u->high_bits = 0;
  } else if (shift_amount <= 0) {
    u->high_bits <<= -shift_amount;
    u->high_bits += u->low_bits >> (64 + shift_amount);
    u->low_bits <<= -shift_amount;
  } else {
    u->low_bits >>= shift_amount;
    u->low_bits += u->high_bits << (64 - shift_amount);
    u->high_bits >>= shift_amount;
  }
}

static int uint128_div_mod_power_of_2(UInt128 *u, int power) {
  if (power >= 64) {
    int result = (int)(u->high_bits >> (power - 64));
    u->high_bits -= (uint64_t)result << (power - 64);
    return result;
  } else {
    uint64_t part_low = u->low_bits >> power;
    uint64_t part_high = u->high_bits << (64 - power);
    int result = (int)(part_low + part_high);
    u->high_bits = 0;
    u->low_bits -= part_low << power;
    return result;
  }
}

static int uint128_is_zero(const UInt128 *u) {
  return u->high_bits == 0 && u->low_bits == 0;
}

static int uint128_bit_at(const UInt128 *u, int position) {
  if (position >= 64) return (int)(u->high_bits >> (position - 64)) & 1;
  return (int)(u->low_bits >> position) & 1;
}

#define FIXED_DTOA_DOUBLE_SIGNIFICAND_SIZE 53

static void fixed_fill_digits32_fixed_length(uint32_t number, int requested_length,
                                              char *buffer, int *length) {
  for (int i = requested_length - 1; i >= 0; --i) {
    buffer[(*length) + i] = (char)('0' + number % 10);
    number /= 10;
  }
  *length += requested_length;
}

static void fixed_fill_digits32(uint32_t number, char *buffer, int *length) {
  int number_length = 0;
  while (number != 0) {
    int digit = number % 10;
    number /= 10;
    buffer[(*length) + number_length] = (char)('0' + digit);
    number_length++;
  }
  int i = *length;
  int j = *length + number_length - 1;
  while (i < j) {
    char tmp = buffer[i];
    buffer[i] = buffer[j];
    buffer[j] = tmp;
    i++; j--;
  }
  *length += number_length;
}

static void fixed_fill_digits64_fixed_length(uint64_t number, char *buffer, int *length) {
  const uint32_t kTen7 = 10000000;
  uint32_t part2 = (uint32_t)(number % kTen7);
  number /= kTen7;
  uint32_t part1 = (uint32_t)(number % kTen7);
  uint32_t part0 = (uint32_t)(number / kTen7);
  fixed_fill_digits32_fixed_length(part0, 3, buffer, length);
  fixed_fill_digits32_fixed_length(part1, 7, buffer, length);
  fixed_fill_digits32_fixed_length(part2, 7, buffer, length);
}

static void fixed_fill_digits64(uint64_t number, char *buffer, int *length) {
  const uint32_t kTen7 = 10000000;
  uint32_t part2 = (uint32_t)(number % kTen7);
  number /= kTen7;
  uint32_t part1 = (uint32_t)(number % kTen7);
  uint32_t part0 = (uint32_t)(number / kTen7);
  if (part0 != 0) {
    fixed_fill_digits32(part0, buffer, length);
    fixed_fill_digits32_fixed_length(part1, 7, buffer, length);
    fixed_fill_digits32_fixed_length(part2, 7, buffer, length);
  } else if (part1 != 0) {
    fixed_fill_digits32(part1, buffer, length);
    fixed_fill_digits32_fixed_length(part2, 7, buffer, length);
  } else {
    fixed_fill_digits32(part2, buffer, length);
  }
}

static void fixed_round_up(char *buffer, int *length, int *decimal_point) {
  if (*length == 0) {
    buffer[0] = '1';
    *decimal_point = 1;
    *length = 1;
    return;
  }
  buffer[(*length) - 1]++;
  for (int i = (*length) - 1; i > 0; --i) {
    if (buffer[i] != '0' + 10) return;
    buffer[i] = '0';
    buffer[i - 1]++;
  }
  if (buffer[0] == '0' + 10) {
    buffer[0] = '1';
    (*decimal_point)++;
  }
}

static void fixed_fill_fractionals(uint64_t fractionals, int exponent,
                                    int fractional_count, char *buffer,
                                    int *length, int *decimal_point) {
  DC_ASSERT(-128 <= exponent && exponent <= 0);
  if (-exponent <= 64) {
    DC_ASSERT(fractionals >> 56 == 0);
    int point = -exponent;
    for (int i = 0; i < fractional_count; ++i) {
      if (fractionals == 0) break;
      fractionals *= 5;
      point--;
      int digit = (int)(fractionals >> point);
      DC_ASSERT(digit <= 9);
      buffer[*length] = (char)('0' + digit);
      (*length)++;
      fractionals -= (uint64_t)digit << point;
    }
    DC_ASSERT(fractionals == 0 || point - 1 >= 0);
    if ((fractionals != 0) && ((fractionals >> (point - 1)) & 1) == 1) {
      fixed_round_up(buffer, length, decimal_point);
    }
  } else {
    DC_ASSERT(64 < -exponent && -exponent <= 128);
    UInt128 fractionals128 = uint128_make(fractionals, 0);
    uint128_shift(&fractionals128, -exponent - 64);
    int point = 128;
    for (int i = 0; i < fractional_count; ++i) {
      if (uint128_is_zero(&fractionals128)) break;
      uint128_multiply(&fractionals128, 5);
      point--;
      int digit = uint128_div_mod_power_of_2(&fractionals128, point);
      DC_ASSERT(digit <= 9);
      buffer[*length] = (char)('0' + digit);
      (*length)++;
    }
    if (uint128_bit_at(&fractionals128, point - 1) == 1) {
      fixed_round_up(buffer, length, decimal_point);
    }
  }
}

static void fixed_trim_zeros(char *buffer, int *length, int *decimal_point) {
  while (*length > 0 && buffer[(*length) - 1] == '0') (*length)--;
  int first_non_zero = 0;
  while (first_non_zero < *length && buffer[first_non_zero] == '0') first_non_zero++;
  if (first_non_zero != 0) {
    for (int i = first_non_zero; i < *length; ++i) buffer[i - first_non_zero] = buffer[i];
    *length -= first_non_zero;
    *decimal_point -= first_non_zero;
  }
}

static int fast_fixed_dtoa(double v, int fractional_count,
                           char *buffer, int *length, int *decimal_point) {
  const uint32_t kMaxUInt32 = 0xFFFFFFFF;
  uint64_t v64 = double_to_uint64(v);
  uint64_t significand = dbl_significand(v64);
  int exponent = dbl_exponent(v64);
  if (exponent > 20) return 0;
  if (fractional_count > 20) return 0;
  *length = 0;
  if (exponent + FIXED_DTOA_DOUBLE_SIGNIFICAND_SIZE > 64) {
    const uint64_t kFive17 = UINT64_2C(0xB1, A2BC2EC5);
    uint64_t divisor = kFive17;
    int divisor_power = 17;
    uint64_t dividend = significand;
    uint32_t quotient;
    uint64_t remainder;
    if (exponent > divisor_power) {
      dividend <<= exponent - divisor_power;
      quotient = (uint32_t)(dividend / divisor);
      remainder = (dividend % divisor) << divisor_power;
    } else {
      divisor <<= divisor_power - exponent;
      quotient = (uint32_t)(dividend / divisor);
      remainder = (dividend % divisor) << exponent;
    }
    fixed_fill_digits32(quotient, buffer, length);
    fixed_fill_digits64_fixed_length(remainder, buffer, length);
    *decimal_point = *length;
  } else if (exponent >= 0) {
    significand <<= exponent;
    fixed_fill_digits64(significand, buffer, length);
    *decimal_point = *length;
  } else if (exponent > -FIXED_DTOA_DOUBLE_SIGNIFICAND_SIZE) {
    uint64_t integrals = significand >> -exponent;
    uint64_t fractionals = significand - (integrals << -exponent);
    if (integrals > kMaxUInt32) {
      fixed_fill_digits64(integrals, buffer, length);
    } else {
      fixed_fill_digits32((uint32_t)integrals, buffer, length);
    }
    *decimal_point = *length;
    fixed_fill_fractionals(fractionals, exponent, fractional_count, buffer, length, decimal_point);
  } else if (exponent < -128) {
    DC_ASSERT(fractional_count <= 20);
    buffer[0] = '\0';
    *length = 0;
    *decimal_point = -fractional_count;
  } else {
    *decimal_point = 0;
    fixed_fill_fractionals(significand, exponent, fractional_count, buffer, length, decimal_point);
  }
  fixed_trim_zeros(buffer, length, decimal_point);
  buffer[*length] = '\0';
  if ((*length) == 0) {
    *decimal_point = -fractional_count;
  }
  return 1;
}

/* ============================================================
 * bignum.h / .cc
 * ============================================================ */

#define BIGNUM_MAX_SIGNIFICANT_BITS 3584
#define BIGNUM_CHUNK_SIZE 32
#define BIGNUM_DOUBLE_CHUNK_SIZE 64
#define BIGNUM_BIGIT_SIZE 28
#define BIGNUM_BIGIT_MASK ((uint32_t)((1u << BIGNUM_BIGIT_SIZE) - 1))
#define BIGNUM_BIGIT_CAPACITY (BIGNUM_MAX_SIGNIFICANT_BITS / BIGNUM_BIGIT_SIZE)

typedef struct {
  int16_t used_bigits;
  int16_t exponent;
  uint32_t bigits[BIGNUM_BIGIT_CAPACITY];
} Bignum;

static void bignum_zero(Bignum *b) {
  b->used_bigits = 0;
  b->exponent = 0;
}

static void bignum_ensure_capacity(int size) {
  if (size > BIGNUM_BIGIT_CAPACITY) DC_UNREACHABLE();
}

static int bignum_bigit_length(const Bignum *b) { return b->used_bigits + b->exponent; }

static void bignum_clamp(Bignum *b) {
  while (b->used_bigits > 0 && b->bigits[b->used_bigits - 1] == 0) b->used_bigits--;
  if (b->used_bigits == 0) b->exponent = 0;
}

static int bignum_is_clamped(const Bignum *b) {
  return b->used_bigits == 0 || b->bigits[b->used_bigits - 1] != 0;
}

static void bignum_align(Bignum *b, const Bignum *other) {
  if (b->exponent > other->exponent) {
    const int zero_bigits = b->exponent - other->exponent;
    bignum_ensure_capacity(b->used_bigits + zero_bigits);
    for (int i = b->used_bigits - 1; i >= 0; --i) b->bigits[i + zero_bigits] = b->bigits[i];
    for (int i = 0; i < zero_bigits; ++i) b->bigits[i] = 0;
    b->used_bigits = (int16_t)(b->used_bigits + zero_bigits);
    b->exponent = (int16_t)(b->exponent - zero_bigits);
    DC_ASSERT(b->used_bigits >= 0);
    DC_ASSERT(b->exponent >= 0);
  }
}

static void bignum_assign_uint16(Bignum *b, uint16_t value) {
  bignum_zero(b);
  if (value > 0) {
    b->bigits[0] = value;
    b->used_bigits = 1;
  }
}

static void bignum_assign_uint64(Bignum *b, uint64_t value) {
  bignum_zero(b);
  int i = 0;
  while (value > 0) {
    b->bigits[i] = value & BIGNUM_BIGIT_MASK;
    value >>= BIGNUM_BIGIT_SIZE;
    ++i;
    b->used_bigits++;
  }
}

static void bignum_assign_bignum(Bignum *b, const Bignum *other) {
  b->exponent = other->exponent;
  for (int i = 0; i < other->used_bigits; ++i) b->bigits[i] = other->bigits[i];
  b->used_bigits = other->used_bigits;
}

static uint64_t bn_read_uint64_range(const char *buffer, int from, int digits_to_read) {
  uint64_t result = 0;
  for (int i = from; i < from + digits_to_read; ++i) {
    const int digit = buffer[i] - '0';
    DC_ASSERT(0 <= digit && digit <= 9);
    result = result * 10 + digit;
  }
  return result;
}

static void bignum_times10(Bignum *b);
static void bignum_multiply_by_power_of_ten(Bignum *b, int exponent);
static void bignum_add_uint64(Bignum *b, uint64_t operand);

static void bignum_assign_decimal_string(Bignum *b, const char *value, int value_len) {
  static const int kMaxUint64DecimalDigits = 19;
  bignum_zero(b);
  int length = value_len;
  int pos = 0;
  while (length >= kMaxUint64DecimalDigits) {
    const uint64_t digits = bn_read_uint64_range(value, pos, kMaxUint64DecimalDigits);
    pos += kMaxUint64DecimalDigits;
    length -= kMaxUint64DecimalDigits;
    bignum_multiply_by_power_of_ten(b, kMaxUint64DecimalDigits);
    bignum_add_uint64(b, digits);
  }
  const uint64_t digits = bn_read_uint64_range(value, pos, length);
  bignum_multiply_by_power_of_ten(b, length);
  bignum_add_uint64(b, digits);
  bignum_clamp(b);
}

static void bignum_add_bignum(Bignum *b, const Bignum *other) {
  DC_ASSERT(bignum_is_clamped(b));
  DC_ASSERT(bignum_is_clamped(other));
  bignum_align(b, other);
  bignum_ensure_capacity(1 + DC_MAX(bignum_bigit_length(b), bignum_bigit_length(other)) - b->exponent);
  uint32_t carry = 0;
  int bigit_pos = other->exponent - b->exponent;
  DC_ASSERT(bigit_pos >= 0);
  for (int i = b->used_bigits; i < bigit_pos; ++i) b->bigits[i] = 0;
  for (int i = 0; i < other->used_bigits; ++i) {
    const uint32_t my = (bigit_pos < b->used_bigits) ? b->bigits[bigit_pos] : 0;
    const uint32_t sum = my + other->bigits[i] + carry;
    b->bigits[bigit_pos] = sum & BIGNUM_BIGIT_MASK;
    carry = sum >> BIGNUM_BIGIT_SIZE;
    ++bigit_pos;
  }
  while (carry != 0) {
    const uint32_t my = (bigit_pos < b->used_bigits) ? b->bigits[bigit_pos] : 0;
    const uint32_t sum = my + carry;
    b->bigits[bigit_pos] = sum & BIGNUM_BIGIT_MASK;
    carry = sum >> BIGNUM_BIGIT_SIZE;
    ++bigit_pos;
  }
  b->used_bigits = (int16_t)DC_MAX(bigit_pos, (int)b->used_bigits);
  DC_ASSERT(bignum_is_clamped(b));
}

static void bignum_add_uint64(Bignum *b, uint64_t operand) {
  if (operand == 0) return;
  Bignum other;
  bignum_assign_uint64(&other, operand);
  bignum_add_bignum(b, &other);
}

static void bignum_subtract_bignum(Bignum *b, const Bignum *other) {
  DC_ASSERT(bignum_is_clamped(b));
  DC_ASSERT(bignum_is_clamped(other));
  bignum_align(b, other);
  const int offset = other->exponent - b->exponent;
  uint32_t borrow = 0;
  int i;
  for (i = 0; i < other->used_bigits; ++i) {
    DC_ASSERT((borrow == 0) || (borrow == 1));
    const uint32_t difference = b->bigits[i + offset] - other->bigits[i] - borrow;
    b->bigits[i + offset] = difference & BIGNUM_BIGIT_MASK;
    borrow = difference >> (BIGNUM_CHUNK_SIZE - 1);
  }
  while (borrow != 0) {
    const uint32_t difference = b->bigits[i + offset] - borrow;
    b->bigits[i + offset] = difference & BIGNUM_BIGIT_MASK;
    borrow = difference >> (BIGNUM_CHUNK_SIZE - 1);
    ++i;
  }
  bignum_clamp(b);
}

static void bignum_bigits_shift_left(Bignum *b, int shift_amount) {
  DC_ASSERT(shift_amount < BIGNUM_BIGIT_SIZE);
  DC_ASSERT(shift_amount >= 0);
  uint32_t carry = 0;
  for (int i = 0; i < b->used_bigits; ++i) {
    const uint32_t new_carry = b->bigits[i] >> (BIGNUM_BIGIT_SIZE - shift_amount);
    b->bigits[i] = ((b->bigits[i] << shift_amount) + carry) & BIGNUM_BIGIT_MASK;
    carry = new_carry;
  }
  if (carry != 0) {
    b->bigits[b->used_bigits] = carry;
    b->used_bigits++;
  }
}

static void bignum_shift_left(Bignum *b, int shift_amount) {
  if (b->used_bigits == 0) return;
  b->exponent = (int16_t)(b->exponent + shift_amount / BIGNUM_BIGIT_SIZE);
  const int local_shift = shift_amount % BIGNUM_BIGIT_SIZE;
  bignum_ensure_capacity(b->used_bigits + 1);
  bignum_bigits_shift_left(b, local_shift);
}

static void bignum_multiply_by_uint32(Bignum *b, uint32_t factor) {
  if (factor == 1) return;
  if (factor == 0) { bignum_zero(b); return; }
  if (b->used_bigits == 0) return;
  uint64_t carry = 0;
  for (int i = 0; i < b->used_bigits; ++i) {
    const uint64_t product = (uint64_t)factor * b->bigits[i] + carry;
    b->bigits[i] = (uint32_t)(product & BIGNUM_BIGIT_MASK);
    carry = product >> BIGNUM_BIGIT_SIZE;
  }
  while (carry != 0) {
    bignum_ensure_capacity(b->used_bigits + 1);
    b->bigits[b->used_bigits] = carry & BIGNUM_BIGIT_MASK;
    b->used_bigits++;
    carry >>= BIGNUM_BIGIT_SIZE;
  }
}

static void bignum_multiply_by_uint64(Bignum *b, uint64_t factor) {
  if (factor == 1) return;
  if (factor == 0) { bignum_zero(b); return; }
  if (b->used_bigits == 0) return;
  DC_ASSERT(BIGNUM_BIGIT_SIZE < 32);
  uint64_t carry = 0;
  const uint64_t low = factor & 0xFFFFFFFF;
  const uint64_t high = factor >> 32;
  for (int i = 0; i < b->used_bigits; ++i) {
    const uint64_t product_low = low * b->bigits[i];
    const uint64_t product_high = high * b->bigits[i];
    const uint64_t tmp = (carry & BIGNUM_BIGIT_MASK) + product_low;
    b->bigits[i] = (uint32_t)(tmp & BIGNUM_BIGIT_MASK);
    carry = (carry >> BIGNUM_BIGIT_SIZE) + (tmp >> BIGNUM_BIGIT_SIZE) +
            (product_high << (32 - BIGNUM_BIGIT_SIZE));
  }
  while (carry != 0) {
    bignum_ensure_capacity(b->used_bigits + 1);
    b->bigits[b->used_bigits] = carry & BIGNUM_BIGIT_MASK;
    b->used_bigits++;
    carry >>= BIGNUM_BIGIT_SIZE;
  }
}

static void bignum_times10(Bignum *b) { bignum_multiply_by_uint32(b, 10); }

#define BN_FIVE1 5
#define BN_FIVE2 (BN_FIVE1 * 5)
#define BN_FIVE3 (BN_FIVE2 * 5)
#define BN_FIVE4 (BN_FIVE3 * 5)
#define BN_FIVE5 (BN_FIVE4 * 5)
#define BN_FIVE6 (BN_FIVE5 * 5)
#define BN_FIVE7 (BN_FIVE6 * 5)
#define BN_FIVE8 (BN_FIVE7 * 5)
#define BN_FIVE9 (BN_FIVE8 * 5)
#define BN_FIVE10 (BN_FIVE9 * 5)
#define BN_FIVE11 (BN_FIVE10 * 5)
#define BN_FIVE12 (BN_FIVE11 * 5)
#define BN_FIVE13 (BN_FIVE12 * 5)

static void bignum_multiply_by_power_of_ten(Bignum *b, int exponent) {
  static const uint64_t kFive27 = UINT64_2C(0x6765c793, fa10079d);
  static const uint32_t kFive13 = BN_FIVE13;
  static const uint32_t kFive1_to_12[] =
      { BN_FIVE1, BN_FIVE2, BN_FIVE3, BN_FIVE4, BN_FIVE5, BN_FIVE6,
        BN_FIVE7, BN_FIVE8, BN_FIVE9, BN_FIVE10, BN_FIVE11, BN_FIVE12 };
  DC_ASSERT(exponent >= 0);
  if (exponent == 0) return;
  if (b->used_bigits == 0) return;
  int remaining_exponent = exponent;
  while (remaining_exponent >= 27) {
    bignum_multiply_by_uint64(b, kFive27);
    remaining_exponent -= 27;
  }
  while (remaining_exponent >= 13) {
    bignum_multiply_by_uint32(b, kFive13);
    remaining_exponent -= 13;
  }
  if (remaining_exponent > 0) {
    bignum_multiply_by_uint32(b, kFive1_to_12[remaining_exponent - 1]);
  }
  bignum_shift_left(b, exponent);
}

static void bignum_square(Bignum *b) {
  DC_ASSERT(bignum_is_clamped(b));
  const int product_length = 2 * b->used_bigits;
  bignum_ensure_capacity(product_length);
  if ((1 << (2 * (BIGNUM_CHUNK_SIZE - BIGNUM_BIGIT_SIZE))) <= b->used_bigits) DC_UNREACHABLE();
  uint64_t accumulator = 0;
  const int copy_offset = b->used_bigits;
  for (int i = 0; i < b->used_bigits; ++i) b->bigits[copy_offset + i] = b->bigits[i];
  for (int i = 0; i < b->used_bigits; ++i) {
    int bigit_index1 = i;
    int bigit_index2 = 0;
    while (bigit_index1 >= 0) {
      const uint32_t chunk1 = b->bigits[copy_offset + bigit_index1];
      const uint32_t chunk2 = b->bigits[copy_offset + bigit_index2];
      accumulator += (uint64_t)chunk1 * chunk2;
      bigit_index1--;
      bigit_index2++;
    }
    b->bigits[i] = (uint32_t)accumulator & BIGNUM_BIGIT_MASK;
    accumulator >>= BIGNUM_BIGIT_SIZE;
  }
  for (int i = b->used_bigits; i < product_length; ++i) {
    int bigit_index1 = b->used_bigits - 1;
    int bigit_index2 = i - bigit_index1;
    while (bigit_index2 < b->used_bigits) {
      const uint32_t chunk1 = b->bigits[copy_offset + bigit_index1];
      const uint32_t chunk2 = b->bigits[copy_offset + bigit_index2];
      accumulator += (uint64_t)chunk1 * chunk2;
      bigit_index1--;
      bigit_index2++;
    }
    b->bigits[i] = (uint32_t)accumulator & BIGNUM_BIGIT_MASK;
    accumulator >>= BIGNUM_BIGIT_SIZE;
  }
  DC_ASSERT(accumulator == 0);
  b->used_bigits = (int16_t)product_length;
  b->exponent *= 2;
  bignum_clamp(b);
}

static void bignum_assign_power_uint16(Bignum *b, uint16_t base, int power_exponent) {
  DC_ASSERT(base != 0);
  DC_ASSERT(power_exponent >= 0);
  if (power_exponent == 0) { bignum_assign_uint16(b, 1); return; }
  bignum_zero(b);
  int shifts = 0;
  while ((base & 1) == 0) { base >>= 1; shifts++; }
  int bit_size = 0;
  int tmp_base = base;
  while (tmp_base != 0) { tmp_base >>= 1; bit_size++; }
  const int final_size = bit_size * power_exponent;
  bignum_ensure_capacity(final_size / BIGNUM_BIGIT_SIZE + 2);
  int mask = 1;
  while (power_exponent >= mask) mask <<= 1;
  mask >>= 2;
  uint64_t this_value = base;
  int delayed_multiplication = 0;
  const uint64_t max_32bits = 0xFFFFFFFF;
  while (mask != 0 && this_value <= max_32bits) {
    this_value = this_value * this_value;
    if ((power_exponent & mask) != 0) {
      DC_ASSERT(bit_size > 0);
      const uint64_t base_bits_mask = ~(((uint64_t)1 << (64 - bit_size)) - 1);
      const int high_bits_zero = (this_value & base_bits_mask) == 0;
      if (high_bits_zero) {
        this_value *= base;
      } else {
        delayed_multiplication = 1;
      }
    }
    mask >>= 1;
  }
  bignum_assign_uint64(b, this_value);
  if (delayed_multiplication) bignum_multiply_by_uint32(b, base);
  while (mask != 0) {
    bignum_square(b);
    if ((power_exponent & mask) != 0) bignum_multiply_by_uint32(b, base);
    mask >>= 1;
  }
  bignum_shift_left(b, shifts * power_exponent);
}

static void bignum_subtract_times(Bignum *b, const Bignum *other, int factor) {
  DC_ASSERT(b->exponent <= other->exponent);
  if (factor < 3) {
    for (int i = 0; i < factor; ++i) bignum_subtract_bignum(b, other);
    return;
  }
  uint32_t borrow = 0;
  const int exponent_diff = other->exponent - b->exponent;
  for (int i = 0; i < other->used_bigits; ++i) {
    const uint64_t product = (uint64_t)factor * other->bigits[i];
    const uint64_t remove = borrow + product;
    const uint32_t difference = b->bigits[i + exponent_diff] - (uint32_t)(remove & BIGNUM_BIGIT_MASK);
    b->bigits[i + exponent_diff] = difference & BIGNUM_BIGIT_MASK;
    borrow = (uint32_t)((difference >> (BIGNUM_CHUNK_SIZE - 1)) + (remove >> BIGNUM_BIGIT_SIZE));
  }
  for (int i = other->used_bigits + exponent_diff; i < b->used_bigits; ++i) {
    if (borrow == 0) return;
    const uint32_t difference = b->bigits[i] - borrow;
    b->bigits[i] = difference & BIGNUM_BIGIT_MASK;
    borrow = difference >> (BIGNUM_CHUNK_SIZE - 1);
  }
  bignum_clamp(b);
}

static uint32_t bignum_bigit_or_zero(const Bignum *b, int index) {
  if (index >= bignum_bigit_length(b)) return 0;
  if (index < b->exponent) return 0;
  return b->bigits[index - b->exponent];
}

static int bignum_compare(const Bignum *a, const Bignum *b) {
  DC_ASSERT(bignum_is_clamped(a));
  DC_ASSERT(bignum_is_clamped(b));
  const int bigit_length_a = bignum_bigit_length(a);
  const int bigit_length_b = bignum_bigit_length(b);
  if (bigit_length_a < bigit_length_b) return -1;
  if (bigit_length_a > bigit_length_b) return +1;
  for (int i = bigit_length_a - 1; i >= DC_MIN(a->exponent, b->exponent); --i) {
    const uint32_t bigit_a = bignum_bigit_or_zero(a, i);
    const uint32_t bigit_b = bignum_bigit_or_zero(b, i);
    if (bigit_a < bigit_b) return -1;
    if (bigit_a > bigit_b) return +1;
  }
  return 0;
}

static int bignum_equal(const Bignum *a, const Bignum *b) { return bignum_compare(a, b) == 0; }
static int bignum_less_equal(const Bignum *a, const Bignum *b) { return bignum_compare(a, b) <= 0; }
static int bignum_less(const Bignum *a, const Bignum *b) { return bignum_compare(a, b) < 0; }

static int bignum_plus_compare(const Bignum *a, const Bignum *b, const Bignum *c) {
  DC_ASSERT(bignum_is_clamped(a));
  DC_ASSERT(bignum_is_clamped(b));
  DC_ASSERT(bignum_is_clamped(c));
  if (bignum_bigit_length(a) < bignum_bigit_length(b)) return bignum_plus_compare(b, a, c);
  if (bignum_bigit_length(a) + 1 < bignum_bigit_length(c)) return -1;
  if (bignum_bigit_length(a) > bignum_bigit_length(c)) return +1;
  if (a->exponent >= bignum_bigit_length(b) && bignum_bigit_length(a) < bignum_bigit_length(c)) return -1;
  uint32_t borrow = 0;
  const int min_exponent = DC_MIN(DC_MIN(a->exponent, b->exponent), c->exponent);
  for (int i = bignum_bigit_length(c) - 1; i >= min_exponent; --i) {
    const uint32_t chunk_a = bignum_bigit_or_zero(a, i);
    const uint32_t chunk_b = bignum_bigit_or_zero(b, i);
    const uint32_t chunk_c = bignum_bigit_or_zero(c, i);
    const uint32_t sum = chunk_a + chunk_b;
    if (sum > chunk_c + borrow) {
      return +1;
    } else {
      borrow = chunk_c + borrow - sum;
      if (borrow > 1) return -1;
      borrow <<= BIGNUM_BIGIT_SIZE;
    }
  }
  if (borrow == 0) return 0;
  return -1;
}

/* Precondition: this/other < 16bit. */
static uint16_t bignum_divide_modulo_int_bignum(Bignum *b, const Bignum *other) {
  DC_ASSERT(bignum_is_clamped(b));
  DC_ASSERT(bignum_is_clamped(other));
  DC_ASSERT(other->used_bigits > 0);
  if (bignum_bigit_length(b) < bignum_bigit_length(other)) return 0;
  bignum_align(b, other);
  uint16_t result = 0;
  while (bignum_bigit_length(b) > bignum_bigit_length(other)) {
    DC_ASSERT(other->bigits[other->used_bigits - 1] >= ((1u << BIGNUM_BIGIT_SIZE) / 16));
    DC_ASSERT(b->bigits[b->used_bigits - 1] < 0x10000);
    result += (uint16_t)b->bigits[b->used_bigits - 1];
    bignum_subtract_times(b, other, (int)b->bigits[b->used_bigits - 1]);
  }
  DC_ASSERT(bignum_bigit_length(b) == bignum_bigit_length(other));
  const uint32_t this_bigit = b->bigits[b->used_bigits - 1];
  const uint32_t other_bigit = other->bigits[other->used_bigits - 1];
  if (other->used_bigits == 1) {
    int quotient = this_bigit / other_bigit;
    b->bigits[b->used_bigits - 1] = this_bigit - other_bigit * quotient;
    DC_ASSERT(quotient < 0x10000);
    result += (uint16_t)quotient;
    bignum_clamp(b);
    return result;
  }
  const int division_estimate = this_bigit / (other_bigit + 1);
  DC_ASSERT(division_estimate < 0x10000);
  result += (uint16_t)division_estimate;
  bignum_subtract_times(b, other, division_estimate);
  if (other_bigit * (uint32_t)(division_estimate + 1) > this_bigit) {
    return result;
  }
  while (bignum_less_equal(other, b)) {
    bignum_subtract_bignum(b, other);
    result++;
  }
  return result;
}

/* ============================================================
 * bignum-dtoa.h / .cc
 * ============================================================ */

typedef enum { BIGNUM_DTOA_SHORTEST, BIGNUM_DTOA_FIXED, BIGNUM_DTOA_PRECISION } BignumDtoaMode;

static int bd_normalized_exponent(uint64_t significand, int exponent) {
  DC_ASSERT(significand != 0);
  while ((significand & DBL_HIDDEN_BIT) == 0) {
    significand <<= 1;
    exponent -= 1;
  }
  return exponent;
}

static int bd_estimate_power(int exponent) {
  const double k1Log10 = 0.30102999566398114;
  const int kSignificandSize = DBL_SIGNIFICAND_SIZE;
  double estimate = ceil((exponent + kSignificandSize - 1) * k1Log10 - 1e-10);
  return (int)estimate;
}

static void bd_initial_scaled_start_values_positive_exponent(
    uint64_t significand, int exponent, int estimated_power, int need_boundary_deltas,
    Bignum *numerator, Bignum *denominator, Bignum *delta_minus, Bignum *delta_plus) {
  DC_ASSERT(estimated_power >= 0);
  bignum_assign_uint64(numerator, significand);
  bignum_shift_left(numerator, exponent);
  bignum_assign_power_uint16(denominator, 10, estimated_power);
  if (need_boundary_deltas) {
    bignum_shift_left(denominator, 1);
    bignum_shift_left(numerator, 1);
    bignum_assign_uint16(delta_plus, 1);
    bignum_shift_left(delta_plus, exponent);
    bignum_assign_uint16(delta_minus, 1);
    bignum_shift_left(delta_minus, exponent);
  }
}

static void bd_initial_scaled_start_values_negative_exponent_positive_power(
    uint64_t significand, int exponent, int estimated_power, int need_boundary_deltas,
    Bignum *numerator, Bignum *denominator, Bignum *delta_minus, Bignum *delta_plus) {
  bignum_assign_uint64(numerator, significand);
  bignum_assign_power_uint16(denominator, 10, estimated_power);
  bignum_shift_left(denominator, -exponent);
  if (need_boundary_deltas) {
    bignum_shift_left(denominator, 1);
    bignum_shift_left(numerator, 1);
    bignum_assign_uint16(delta_plus, 1);
    bignum_assign_uint16(delta_minus, 1);
  }
}

static void bd_initial_scaled_start_values_negative_exponent_negative_power(
    uint64_t significand, int exponent, int estimated_power, int need_boundary_deltas,
    Bignum *numerator, Bignum *denominator, Bignum *delta_minus, Bignum *delta_plus) {
  Bignum *power_ten = numerator;
  bignum_assign_power_uint16(power_ten, 10, -estimated_power);
  if (need_boundary_deltas) {
    bignum_assign_bignum(delta_plus, power_ten);
    bignum_assign_bignum(delta_minus, power_ten);
  }
  bignum_multiply_by_uint64(numerator, significand);
  bignum_assign_uint16(denominator, 1);
  bignum_shift_left(denominator, -exponent);
  if (need_boundary_deltas) {
    bignum_shift_left(numerator, 1);
    bignum_shift_left(denominator, 1);
  }
}

static void bd_initial_scaled_start_values(
    uint64_t significand, int exponent, int lower_boundary_is_closer,
    int estimated_power, int need_boundary_deltas,
    Bignum *numerator, Bignum *denominator, Bignum *delta_minus, Bignum *delta_plus) {
  if (exponent >= 0) {
    bd_initial_scaled_start_values_positive_exponent(
        significand, exponent, estimated_power, need_boundary_deltas,
        numerator, denominator, delta_minus, delta_plus);
  } else if (estimated_power >= 0) {
    bd_initial_scaled_start_values_negative_exponent_positive_power(
        significand, exponent, estimated_power, need_boundary_deltas,
        numerator, denominator, delta_minus, delta_plus);
  } else {
    bd_initial_scaled_start_values_negative_exponent_negative_power(
        significand, exponent, estimated_power, need_boundary_deltas,
        numerator, denominator, delta_minus, delta_plus);
  }
  if (need_boundary_deltas && lower_boundary_is_closer) {
    bignum_shift_left(denominator, 1);
    bignum_shift_left(numerator, 1);
    bignum_shift_left(delta_plus, 1);
  }
}

static void bd_fixup_multiply10(int estimated_power, int is_even, int *decimal_point,
                                 Bignum *numerator, Bignum *denominator,
                                 Bignum *delta_minus, Bignum *delta_plus) {
  int in_range;
  if (is_even) {
    in_range = bignum_plus_compare(numerator, delta_plus, denominator) >= 0;
  } else {
    in_range = bignum_plus_compare(numerator, delta_plus, denominator) > 0;
  }
  if (in_range) {
    *decimal_point = estimated_power + 1;
  } else {
    *decimal_point = estimated_power;
    bignum_times10(numerator);
    if (bignum_equal(delta_minus, delta_plus)) {
      bignum_times10(delta_minus);
      bignum_assign_bignum(delta_plus, delta_minus);
    } else {
      bignum_times10(delta_minus);
      bignum_times10(delta_plus);
    }
  }
}

static void bd_generate_shortest_digits(Bignum *numerator, Bignum *denominator,
                                         Bignum *delta_minus, Bignum *delta_plus,
                                         int is_even, char *buffer, int *length) {
  if (bignum_equal(delta_minus, delta_plus)) delta_plus = delta_minus;
  *length = 0;
  for (;;) {
    uint16_t digit = bignum_divide_modulo_int_bignum(numerator, denominator);
    DC_ASSERT(digit <= 9);
    buffer[(*length)++] = (char)(digit + '0');
    int in_delta_room_minus;
    int in_delta_room_plus;
    if (is_even) {
      in_delta_room_minus = bignum_less_equal(numerator, delta_minus);
    } else {
      in_delta_room_minus = bignum_less(numerator, delta_minus);
    }
    if (is_even) {
      in_delta_room_plus = bignum_plus_compare(numerator, delta_plus, denominator) >= 0;
    } else {
      in_delta_room_plus = bignum_plus_compare(numerator, delta_plus, denominator) > 0;
    }
    if (!in_delta_room_minus && !in_delta_room_plus) {
      bignum_times10(numerator);
      bignum_times10(delta_minus);
      if (delta_minus != delta_plus) bignum_times10(delta_plus);
    } else if (in_delta_room_minus && in_delta_room_plus) {
      int compare = bignum_plus_compare(numerator, numerator, denominator);
      if (compare < 0) {
        /* round down */
      } else if (compare > 0) {
        DC_ASSERT(buffer[(*length) - 1] != '9');
        buffer[(*length) - 1]++;
      } else {
        if ((buffer[(*length) - 1] - '0') % 2 == 0) {
          /* round down */
        } else {
          DC_ASSERT(buffer[(*length) - 1] != '9');
          buffer[(*length) - 1]++;
        }
      }
      return;
    } else if (in_delta_room_minus) {
      return;
    } else {
      DC_ASSERT(buffer[(*length) - 1] != '9');
      buffer[(*length) - 1]++;
      return;
    }
  }
}

static void bd_generate_counted_digits(int count, int *decimal_point,
                                        Bignum *numerator, Bignum *denominator,
                                        char *buffer, int *length) {
  DC_ASSERT(count >= 0);
  for (int i = 0; i < count - 1; ++i) {
    uint16_t digit = bignum_divide_modulo_int_bignum(numerator, denominator);
    DC_ASSERT(digit <= 9);
    buffer[i] = (char)(digit + '0');
    bignum_times10(numerator);
  }
  uint16_t digit = bignum_divide_modulo_int_bignum(numerator, denominator);
  if (bignum_plus_compare(numerator, numerator, denominator) >= 0) digit++;
  DC_ASSERT(digit <= 10);
  buffer[count - 1] = (char)(digit + '0');
  for (int i = count - 1; i > 0; --i) {
    if (buffer[i] != '0' + 10) break;
    buffer[i] = '0';
    buffer[i - 1]++;
  }
  if (buffer[0] == '0' + 10) {
    buffer[0] = '1';
    (*decimal_point)++;
  }
  *length = count;
}

static void bd_bignum_to_fixed(int requested_digits, int *decimal_point,
                                Bignum *numerator, Bignum *denominator,
                                char *buffer, int *length) {
  if (-(*decimal_point) > requested_digits) {
    *decimal_point = -requested_digits;
    *length = 0;
    return;
  } else if (-(*decimal_point) == requested_digits) {
    DC_ASSERT(*decimal_point == -requested_digits);
    bignum_times10(denominator);
    if (bignum_plus_compare(numerator, numerator, denominator) >= 0) {
      buffer[0] = '1';
      *length = 1;
      (*decimal_point)++;
    } else {
      *length = 0;
    }
    return;
  } else {
    int needed_digits = (*decimal_point) + requested_digits;
    bd_generate_counted_digits(needed_digits, decimal_point, numerator, denominator, buffer, length);
  }
}

static void bignum_dtoa(double v, BignumDtoaMode mode, int requested_digits,
                        char *buffer, int *length, int *decimal_point) {
  DC_ASSERT(v > 0);
  uint64_t v64 = double_to_uint64(v);
  DC_ASSERT(!dbl_is_special(v64));
  uint64_t significand = dbl_significand(v64);
  int exponent = dbl_exponent(v64);
  int lower_boundary_is_closer = dbl_lower_boundary_is_closer(v64);
  int need_boundary_deltas = (mode == BIGNUM_DTOA_SHORTEST);
  int is_even = (significand & 1) == 0;
  int normalized_exponent = bd_normalized_exponent(significand, exponent);
  int estimated_power = bd_estimate_power(normalized_exponent);

  if (mode == BIGNUM_DTOA_FIXED && -estimated_power - 1 > requested_digits) {
    buffer[0] = '\0';
    *length = 0;
    *decimal_point = -requested_digits;
    return;
  }

  Bignum numerator, denominator, delta_minus, delta_plus;
  /* C++ Bignum's default ctor zeroes used_bigits_/exponent_; a C stack Bignum
   * does not. For non-shortest modes the deltas are never assigned (see
   * bd_initial_scaled_start_values), so zero them here or fixup_multiply10 reads
   * garbage and bignum_plus_compare's is_clamped assertion trips. */
  bignum_zero(&numerator);
  bignum_zero(&denominator);
  bignum_zero(&delta_minus);
  bignum_zero(&delta_plus);
  DC_ASSERT(BIGNUM_MAX_SIGNIFICANT_BITS >= 324 * 4);
  bd_initial_scaled_start_values(significand, exponent, lower_boundary_is_closer,
                                 estimated_power, need_boundary_deltas,
                                 &numerator, &denominator, &delta_minus, &delta_plus);
  bd_fixup_multiply10(estimated_power, is_even, decimal_point,
                       &numerator, &denominator, &delta_minus, &delta_plus);
  switch (mode) {
    case BIGNUM_DTOA_SHORTEST:
      bd_generate_shortest_digits(&numerator, &denominator, &delta_minus, &delta_plus,
                                   is_even, buffer, length);
      break;
    case BIGNUM_DTOA_FIXED:
      bd_bignum_to_fixed(requested_digits, decimal_point, &numerator, &denominator, buffer, length);
      break;
    case BIGNUM_DTOA_PRECISION:
      bd_generate_counted_digits(requested_digits, decimal_point, &numerator, &denominator, buffer, length);
      break;
    default:
      DC_UNREACHABLE();
  }
  buffer[*length] = '\0';
}

/* ============================================================
 * double-to-string.h / .cc  (EcmaScript converter hardcoded)
 * ============================================================ */

#define DTS_FLAG_EMIT_POSITIVE_EXPONENT_SIGN 1
#define DTS_FLAG_UNIQUE_ZERO 8
/* Hardcoded EcmaScriptConverter() config: */
#define DTS_FLAGS (DTS_FLAG_UNIQUE_ZERO | DTS_FLAG_EMIT_POSITIVE_EXPONENT_SIGN)
static const char *const DTS_INFINITY_SYMBOL = "Infinity";
static const char *const DTS_NAN_SYMBOL = "NaN";
#define DTS_EXPONENT_CHARACTER 'e'
#define DTS_DECIMAL_IN_SHORTEST_LOW (-6)
#define DTS_DECIMAL_IN_SHORTEST_HIGH 21
#define DTS_MAX_LEADING_PADDING_ZEROES_IN_PRECISION 6
#define DTS_MAX_TRAILING_PADDING_ZEROES_IN_PRECISION 0
#define DTS_MIN_EXPONENT_WIDTH 0

#define DTS_MAX_FIXED_DIGITS_BEFORE_POINT 60
#define DTS_MAX_FIXED_DIGITS_AFTER_POINT 100
#define DTS_MAX_EXPONENTIAL_DIGITS 120
#define DTS_MIN_PRECISION_DIGITS 1
#define DTS_MAX_PRECISION_DIGITS 120
#define DTS_BASE10_MAXIMAL_LENGTH 17

typedef enum { DTOA_SHORTEST, DTOA_FIXED, DTOA_PRECISION } DtoaMode;

static int dts_handle_special_values(double value, StringBuilder *rb) {
  uint64_t v64 = double_to_uint64(value);
  if (dbl_is_infinite(v64)) {
    if (value < 0) sb_add_character(rb, '-');
    sb_add_string(rb, DTS_INFINITY_SYMBOL);
    return 1;
  }
  if (dbl_is_nan(v64)) {
    sb_add_string(rb, DTS_NAN_SYMBOL);
    return 1;
  }
  return 0;
}

static void dts_create_exponential_representation(const char *decimal_digits, int length,
                                                   int exponent, StringBuilder *rb) {
  DC_ASSERT(length != 0);
  sb_add_character(rb, decimal_digits[0]);
  if (length == 1) {
    /* EMIT_TRAILING_DECIMAL_POINT_IN_EXPONENTIAL not set for EcmaScript converter. */
  } else {
    sb_add_character(rb, '.');
    sb_add_substring(rb, &decimal_digits[1], length - 1);
  }
  sb_add_character(rb, DTS_EXPONENT_CHARACTER);
  if (exponent < 0) {
    sb_add_character(rb, '-');
    exponent = -exponent;
  } else {
    if ((DTS_FLAGS & DTS_FLAG_EMIT_POSITIVE_EXPONENT_SIGN) != 0) sb_add_character(rb, '+');
  }
  DC_ASSERT(exponent < 1e4);
  const int kMaxExponentLength = 5;
  char buffer[6];
  buffer[kMaxExponentLength] = '\0';
  int first_char_pos = kMaxExponentLength;
  if (exponent == 0) {
    buffer[--first_char_pos] = '0';
  } else {
    while (exponent > 0) {
      buffer[--first_char_pos] = (char)('0' + (exponent % 10));
      exponent /= 10;
    }
  }
  while (kMaxExponentLength - first_char_pos < DC_MIN(DTS_MIN_EXPONENT_WIDTH, kMaxExponentLength)) {
    buffer[--first_char_pos] = '0';
  }
  sb_add_substring(rb, &buffer[first_char_pos], kMaxExponentLength - first_char_pos);
}

static void dts_create_decimal_representation(const char *decimal_digits, int length,
                                               int decimal_point, int digits_after_point,
                                               StringBuilder *rb) {
  if (decimal_point <= 0) {
    sb_add_character(rb, '0');
    if (digits_after_point > 0) {
      sb_add_character(rb, '.');
      sb_add_padding(rb, '0', -decimal_point);
      DC_ASSERT(length <= digits_after_point - (-decimal_point));
      sb_add_substring(rb, decimal_digits, length);
      int remaining_digits = digits_after_point - (-decimal_point) - length;
      sb_add_padding(rb, '0', remaining_digits);
    }
  } else if (decimal_point >= length) {
    sb_add_substring(rb, decimal_digits, length);
    sb_add_padding(rb, '0', decimal_point - length);
    if (digits_after_point > 0) {
      sb_add_character(rb, '.');
      sb_add_padding(rb, '0', digits_after_point);
    }
  } else {
    DC_ASSERT(digits_after_point > 0);
    sb_add_substring(rb, decimal_digits, decimal_point);
    sb_add_character(rb, '.');
    DC_ASSERT(length - decimal_point <= digits_after_point);
    sb_add_substring(rb, &decimal_digits[decimal_point], length - decimal_point);
    int remaining_digits = digits_after_point - (length - decimal_point);
    sb_add_padding(rb, '0', remaining_digits);
  }
  /* digits_after_point==0 tail flags (EMIT_TRAILING_DECIMAL_POINT / _ZERO) not set for EcmaScript. */
}

static void dts_double_to_ascii(double v, DtoaMode mode, int requested_digits,
                                 char *buffer, int buffer_length,
                                 int *sign, int *length, int *point) {
  (void)buffer_length;
  uint64_t v64 = double_to_uint64(v);
  DC_ASSERT(!dbl_is_special(v64));
  DC_ASSERT(mode == DTOA_SHORTEST || requested_digits >= 0);

  if (dbl_sign(v64) < 0) {
    *sign = 1;
    v = -v;
  } else {
    *sign = 0;
  }

  if (mode == DTOA_PRECISION && requested_digits == 0) {
    buffer[0] = '\0';
    *length = 0;
    *point = 0;
    return;
  }

  if (v == 0) {
    buffer[0] = '0';
    buffer[1] = '\0';
    *length = 1;
    *point = 1;
    return;
  }

  int fast_worked;
  switch (mode) {
    case DTOA_SHORTEST:
      fast_worked = fast_dtoa(v, FAST_DTOA_SHORTEST, 0, buffer, length, point);
      break;
    case DTOA_FIXED:
      fast_worked = fast_fixed_dtoa(v, requested_digits, buffer, length, point);
      break;
    case DTOA_PRECISION:
      fast_worked = fast_dtoa(v, FAST_DTOA_PRECISION, requested_digits, buffer, length, point);
      break;
    default:
      fast_worked = 0;
      DC_UNREACHABLE();
  }
  if (fast_worked) return;

  BignumDtoaMode bignum_mode;
  switch (mode) {
    case DTOA_SHORTEST: bignum_mode = BIGNUM_DTOA_SHORTEST; break;
    case DTOA_FIXED: bignum_mode = BIGNUM_DTOA_FIXED; break;
    case DTOA_PRECISION: bignum_mode = BIGNUM_DTOA_PRECISION; break;
    default: DC_UNREACHABLE(); bignum_mode = BIGNUM_DTOA_SHORTEST;
  }
  bignum_dtoa(v, bignum_mode, requested_digits, buffer, length, point);
  buffer[*length] = '\0';
}

static int dts_to_shortest(double value, StringBuilder *rb) {
  uint64_t v64 = double_to_uint64(value);
  if (dbl_is_special(v64)) return dts_handle_special_values(value, rb);

  int decimal_point = 0;
  int sign;
  const int kDecimalRepCapacity = DTS_BASE10_MAXIMAL_LENGTH + 1;
  char decimal_rep[DTS_BASE10_MAXIMAL_LENGTH + 1];
  int decimal_rep_length;

  dts_double_to_ascii(value, DTOA_SHORTEST, 0, decimal_rep, kDecimalRepCapacity,
                       &sign, &decimal_rep_length, &decimal_point);

  int unique_zero = (DTS_FLAGS & DTS_FLAG_UNIQUE_ZERO) != 0;
  if (sign && (value != 0.0 || !unique_zero)) sb_add_character(rb, '-');

  int exponent = decimal_point - 1;
  if ((DTS_DECIMAL_IN_SHORTEST_LOW <= exponent) && (exponent < DTS_DECIMAL_IN_SHORTEST_HIGH)) {
    dts_create_decimal_representation(decimal_rep, decimal_rep_length, decimal_point,
                                       DC_MAX(0, decimal_rep_length - decimal_point), rb);
  } else {
    dts_create_exponential_representation(decimal_rep, decimal_rep_length, exponent, rb);
  }
  return 1;
}

static int dts_to_fixed(double value, int requested_digits, StringBuilder *rb) {
  DC_ASSERT(DTS_MAX_FIXED_DIGITS_BEFORE_POINT == 60);
  const double kFirstNonFixed = 1e60;

  uint64_t v64 = double_to_uint64(value);
  if (dbl_is_special(v64)) return dts_handle_special_values(value, rb);

  if (requested_digits > DTS_MAX_FIXED_DIGITS_AFTER_POINT) return 0;
  if (value >= kFirstNonFixed || value <= -kFirstNonFixed) return 0;

  int decimal_point;
  int sign;
  const int kDecimalRepCapacity = DTS_MAX_FIXED_DIGITS_BEFORE_POINT + DTS_MAX_FIXED_DIGITS_AFTER_POINT + 1;
  char decimal_rep[DTS_MAX_FIXED_DIGITS_BEFORE_POINT + DTS_MAX_FIXED_DIGITS_AFTER_POINT + 1];
  int decimal_rep_length;
  dts_double_to_ascii(value, DTOA_FIXED, requested_digits, decimal_rep, kDecimalRepCapacity,
                       &sign, &decimal_rep_length, &decimal_point);

  int unique_zero = (DTS_FLAGS & DTS_FLAG_UNIQUE_ZERO) != 0;
  if (sign && (value != 0.0 || !unique_zero)) sb_add_character(rb, '-');

  dts_create_decimal_representation(decimal_rep, decimal_rep_length, decimal_point,
                                     requested_digits, rb);
  return 1;
}

static int dts_to_exponential(double value, int requested_digits, StringBuilder *rb) {
  uint64_t v64 = double_to_uint64(value);
  if (dbl_is_special(v64)) return dts_handle_special_values(value, rb);

  if (requested_digits < -1) return 0;
  if (requested_digits > DTS_MAX_EXPONENTIAL_DIGITS) return 0;

  int decimal_point;
  int sign;
  const int kDecimalRepCapacity = DTS_MAX_EXPONENTIAL_DIGITS + 2;
  char decimal_rep[DTS_MAX_EXPONENTIAL_DIGITS + 2];
  memset(decimal_rep, 0, sizeof(decimal_rep));
  int decimal_rep_length;

  if (requested_digits == -1) {
    dts_double_to_ascii(value, DTOA_SHORTEST, 0, decimal_rep, kDecimalRepCapacity,
                         &sign, &decimal_rep_length, &decimal_point);
  } else {
    dts_double_to_ascii(value, DTOA_PRECISION, requested_digits + 1, decimal_rep, kDecimalRepCapacity,
                         &sign, &decimal_rep_length, &decimal_point);
    DC_ASSERT(decimal_rep_length <= requested_digits + 1);
    for (int i = decimal_rep_length; i < requested_digits + 1; ++i) decimal_rep[i] = '0';
    decimal_rep_length = requested_digits + 1;
  }

  int unique_zero = (DTS_FLAGS & DTS_FLAG_UNIQUE_ZERO) != 0;
  if (sign && (value != 0.0 || !unique_zero)) sb_add_character(rb, '-');

  int exponent = decimal_point - 1;
  dts_create_exponential_representation(decimal_rep, decimal_rep_length, exponent, rb);
  return 1;
}

static int dts_to_precision(double value, int precision, StringBuilder *rb) {
  uint64_t v64 = double_to_uint64(value);
  if (dbl_is_special(v64)) return dts_handle_special_values(value, rb);

  if (precision < DTS_MIN_PRECISION_DIGITS || precision > DTS_MAX_PRECISION_DIGITS) return 0;

  int decimal_point;
  int sign;
  const int kDecimalRepCapacity = DTS_MAX_PRECISION_DIGITS + 1;
  char decimal_rep[DTS_MAX_PRECISION_DIGITS + 1];
  int decimal_rep_length;

  dts_double_to_ascii(value, DTOA_PRECISION, precision, decimal_rep, kDecimalRepCapacity,
                       &sign, &decimal_rep_length, &decimal_point);
  DC_ASSERT(decimal_rep_length <= precision);

  int unique_zero = (DTS_FLAGS & DTS_FLAG_UNIQUE_ZERO) != 0;
  if (sign && (value != 0.0 || !unique_zero)) sb_add_character(rb, '-');

  int exponent = decimal_point - 1;

  int extra_zero = 0; /* EMIT_TRAILING_ZERO_AFTER_POINT not set. */
  int as_exponential =
      (-decimal_point + 1 > DTS_MAX_LEADING_PADDING_ZEROES_IN_PRECISION) ||
      (decimal_point - precision + extra_zero > DTS_MAX_TRAILING_PADDING_ZEROES_IN_PRECISION);
  /* NO_TRAILING_ZERO not set for EcmaScript converter. */
  if (as_exponential) {
    for (int i = decimal_rep_length; i < precision; ++i) decimal_rep[i] = '0';
    dts_create_exponential_representation(decimal_rep, precision, exponent, rb);
  } else {
    dts_create_decimal_representation(decimal_rep, decimal_rep_length, decimal_point,
                                       DC_MAX(0, precision - decimal_point), rb);
  }
  return 1;
}

/* ============================================================
 * strtod.h / .cc  (double only)
 * ============================================================ */

#define STRTOD_MAX_UINT64_DECIMAL_DIGITS 19
#define STRTOD_MAX_DECIMAL_POWER 309
#define STRTOD_MIN_DECIMAL_POWER (-324)
#define STRTOD_MAX_SIGNIFICANT_DECIMAL_DIGITS 780
#define STRTOD_MAX_EXACT_DOUBLE_INTEGER_DECIMAL_DIGITS 15

static const double kExactPowersOfTen[] = {
  1.0, 10.0, 100.0, 1000.0, 10000.0, 100000.0, 1000000.0,
  10000000.0, 100000000.0, 1000000000.0, 10000000000.0,
  100000000000.0, 1000000000000.0, 10000000000000.0,
  100000000000000.0, 1000000000000000.0, 10000000000000000.0,
  100000000000000000.0, 1000000000000000000.0, 10000000000000000000.0,
  100000000000000000000.0, 1000000000000000000000.0, 10000000000000000000000.0
};
#define STRTOD_EXACT_POWERS_OF_TEN_SIZE ((int)(sizeof(kExactPowersOfTen)/sizeof(kExactPowersOfTen[0])))

static int strtod_trim_trailing_zeros_len(const char *buffer, int len) {
  for (int i = len - 1; i >= 0; --i) {
    if (buffer[i] != '0') return i + 1;
  }
  return 0;
}

static int strtod_trim_leading_zeros_start(const char *buffer, int len) {
  for (int i = 0; i < len; i++) {
    if (buffer[i] != '0') return i;
  }
  return len;
}

static void strtod_cut_to_max_significant_digits(const char *buffer, int buffer_len, int exponent,
                                                   char *significant_buffer, int *significant_exponent) {
  for (int i = 0; i < STRTOD_MAX_SIGNIFICANT_DECIMAL_DIGITS - 1; ++i) {
    significant_buffer[i] = buffer[i];
  }
  DC_ASSERT(buffer[buffer_len - 1] != '0');
  significant_buffer[STRTOD_MAX_SIGNIFICANT_DECIMAL_DIGITS - 1] = '1';
  *significant_exponent = exponent + (buffer_len - STRTOD_MAX_SIGNIFICANT_DECIMAL_DIGITS);
}

static void strtod_trim_and_cut(const char *buffer, int buffer_len, int exponent,
                                 char *buffer_copy_space, int space_size,
                                 const char **trimmed, int *trimmed_len, int *updated_exponent) {
  int lstart = strtod_trim_leading_zeros_start(buffer, buffer_len);
  const char *left_trimmed = buffer + lstart;
  int left_trimmed_len = buffer_len - lstart;
  int right_trimmed_len = strtod_trim_trailing_zeros_len(left_trimmed, left_trimmed_len);
  exponent += left_trimmed_len - right_trimmed_len;
  if (right_trimmed_len > STRTOD_MAX_SIGNIFICANT_DECIMAL_DIGITS) {
    DC_ASSERT(space_size >= STRTOD_MAX_SIGNIFICANT_DECIMAL_DIGITS);
    strtod_cut_to_max_significant_digits(left_trimmed, right_trimmed_len, exponent,
                                          buffer_copy_space, updated_exponent);
    *trimmed = buffer_copy_space;
    *trimmed_len = STRTOD_MAX_SIGNIFICANT_DECIMAL_DIGITS;
  } else {
    *trimmed = left_trimmed;
    *trimmed_len = right_trimmed_len;
    *updated_exponent = exponent;
  }
}

static uint64_t strtod_read_uint64(const char *buffer, int len, int *number_of_read_digits) {
  const uint64_t kMaxUint64 = UINT64_2C(0xFFFFFFFF, FFFFFFFF);
  uint64_t result = 0;
  int i = 0;
  while (i < len && result <= (kMaxUint64 / 10 - 1)) {
    int digit = buffer[i++] - '0';
    DC_ASSERT(0 <= digit && digit <= 9);
    result = 10 * result + digit;
  }
  *number_of_read_digits = i;
  return result;
}

static void strtod_read_diy_fp(const char *buffer, int len, DiyFp *result, int *remaining_decimals) {
  int read_digits;
  uint64_t significand = strtod_read_uint64(buffer, len, &read_digits);
  if (len == read_digits) {
    *result = diyfp_make(significand, 0);
    *remaining_decimals = 0;
  } else {
    if (buffer[read_digits] >= '5') significand++;
    *result = diyfp_make(significand, 0);
    *remaining_decimals = len - read_digits;
  }
}

static int strtod_double_strtod(const char *trimmed, int trimmed_len, int exponent, double *result) {
  if (trimmed_len <= STRTOD_MAX_EXACT_DOUBLE_INTEGER_DECIMAL_DIGITS) {
    int read_digits;
    if (exponent < 0 && -exponent < STRTOD_EXACT_POWERS_OF_TEN_SIZE) {
      *result = (double)strtod_read_uint64(trimmed, trimmed_len, &read_digits);
      DC_ASSERT(read_digits == trimmed_len);
      *result /= kExactPowersOfTen[-exponent];
      return 1;
    }
    if (0 <= exponent && exponent < STRTOD_EXACT_POWERS_OF_TEN_SIZE) {
      *result = (double)strtod_read_uint64(trimmed, trimmed_len, &read_digits);
      DC_ASSERT(read_digits == trimmed_len);
      *result *= kExactPowersOfTen[exponent];
      return 1;
    }
    int remaining_digits = STRTOD_MAX_EXACT_DOUBLE_INTEGER_DECIMAL_DIGITS - trimmed_len;
    if ((0 <= exponent) && (exponent - remaining_digits < STRTOD_EXACT_POWERS_OF_TEN_SIZE)) {
      *result = (double)strtod_read_uint64(trimmed, trimmed_len, &read_digits);
      DC_ASSERT(read_digits == trimmed_len);
      *result *= kExactPowersOfTen[remaining_digits];
      *result *= kExactPowersOfTen[exponent - remaining_digits];
      return 1;
    }
  }
  return 0;
}

static DiyFp strtod_adjustment_power_of_ten(int exponent) {
  DC_ASSERT(0 < exponent);
  DC_ASSERT(exponent < CACHED_POWERS_DECIMAL_EXPONENT_DISTANCE);
  switch (exponent) {
    case 1: return diyfp_make(UINT64_2C(0xa0000000, 00000000), -60);
    case 2: return diyfp_make(UINT64_2C(0xc8000000, 00000000), -57);
    case 3: return diyfp_make(UINT64_2C(0xfa000000, 00000000), -54);
    case 4: return diyfp_make(UINT64_2C(0x9c400000, 00000000), -50);
    case 5: return diyfp_make(UINT64_2C(0xc3500000, 00000000), -47);
    case 6: return diyfp_make(UINT64_2C(0xf4240000, 00000000), -44);
    case 7: return diyfp_make(UINT64_2C(0x98968000, 00000000), -40);
    default:
      DC_UNREACHABLE();
      return diyfp_make(0, 0);
  }
}

static int strtod_diy_fp_strtod(const char *buffer, int buffer_len, int exponent, double *result) {
  DiyFp input;
  int remaining_decimals;
  strtod_read_diy_fp(buffer, buffer_len, &input, &remaining_decimals);
  const int kDenominatorLog = 3;
  const int kDenominator = 1 << kDenominatorLog;
  exponent += remaining_decimals;
  uint64_t error = (remaining_decimals == 0 ? 0 : (uint64_t)(kDenominator / 2));

  int old_e = input.e;
  diyfp_normalize(&input);
  error <<= old_e - input.e;

  DC_ASSERT(exponent <= CACHED_POWERS_MAX_DECIMAL_EXPONENT);
  if (exponent < CACHED_POWERS_MIN_DECIMAL_EXPONENT) {
    *result = 0.0;
    return 1;
  }
  DiyFp cached_power;
  int cached_decimal_exponent;
  get_cached_power_for_decimal_exponent(exponent, &cached_power, &cached_decimal_exponent);

  if (cached_decimal_exponent != exponent) {
    int adjustment_exponent = exponent - cached_decimal_exponent;
    DiyFp adjustment_power = strtod_adjustment_power_of_ten(adjustment_exponent);
    diyfp_multiply(&input, &adjustment_power);
    if (STRTOD_MAX_UINT64_DECIMAL_DIGITS - buffer_len >= adjustment_exponent) {
      DC_ASSERT(DIYFP_SIGNIFICAND_SIZE == 64);
    } else {
      error += (uint64_t)(kDenominator / 2);
    }
  }

  diyfp_multiply(&input, &cached_power);
  int error_b = kDenominator / 2;
  int error_ab = (error == 0 ? 0 : 1);
  int fixed_error = kDenominator / 2;
  error += (uint64_t)(error_b + error_ab + fixed_error);

  old_e = input.e;
  diyfp_normalize(&input);
  error <<= old_e - input.e;

  int order_of_magnitude = DIYFP_SIGNIFICAND_SIZE + input.e;
  int effective_significand_size = dbl_significand_size_for_order_of_magnitude(order_of_magnitude);
  int precision_digits_count = DIYFP_SIGNIFICAND_SIZE - effective_significand_size;
  if (precision_digits_count + kDenominatorLog >= DIYFP_SIGNIFICAND_SIZE) {
    int shift_amount = (precision_digits_count + kDenominatorLog) - DIYFP_SIGNIFICAND_SIZE + 1;
    input.f = input.f >> shift_amount;
    input.e = input.e + shift_amount;
    error = (error >> shift_amount) + 1 + (uint64_t)kDenominator;
    precision_digits_count -= shift_amount;
  }
  DC_ASSERT(DIYFP_SIGNIFICAND_SIZE == 64);
  DC_ASSERT(precision_digits_count < 64);
  uint64_t one64 = 1;
  uint64_t precision_bits_mask = (one64 << precision_digits_count) - 1;
  uint64_t precision_bits = input.f & precision_bits_mask;
  uint64_t half_way = one64 << (precision_digits_count - 1);
  precision_bits *= (uint64_t)kDenominator;
  half_way *= (uint64_t)kDenominator;
  DiyFp rounded_input = diyfp_make(input.f >> precision_digits_count, input.e + precision_digits_count);
  if (precision_bits >= half_way + error) {
    rounded_input.f = rounded_input.f + 1;
  }

  *result = dbl_value(double_to_uint64(0) /* placeholder, replaced below */);
  {
    /* Compute Double(rounded_input).value() : construct bits via DiyFpToUint64 */
    uint64_t significand = rounded_input.f;
    int exp = rounded_input.e;
    while (significand > DBL_HIDDEN_BIT + DBL_SIGNIFICAND_MASK) {
      significand >>= 1;
      exp++;
    }
    uint64_t bits;
    if (exp >= DBL_MAX_EXPONENT) {
      bits = DBL_INFINITY_BITS;
    } else if (exp < DBL_DENORMAL_EXPONENT) {
      bits = 0;
    } else {
      while (exp > DBL_DENORMAL_EXPONENT && (significand & DBL_HIDDEN_BIT) == 0) {
        significand <<= 1;
        exp--;
      }
      uint64_t biased_exponent;
      if (exp == DBL_DENORMAL_EXPONENT && (significand & DBL_HIDDEN_BIT) == 0) {
        biased_exponent = 0;
      } else {
        biased_exponent = (uint64_t)(exp + DBL_EXPONENT_BIAS);
      }
      bits = (significand & DBL_SIGNIFICAND_MASK) | (biased_exponent << DBL_PHYSICAL_SIGNIFICAND_SIZE);
    }
    *result = dbl_value(bits);
  }

  if (half_way - error < precision_bits && precision_bits < half_way + error) {
    return 0;
  }
  return 1;
}

static int strtod_compare_buffer_with_diy_fp(const char *buffer, int buffer_len, int exponent, DiyFp diy_fp) {
  Bignum buffer_bignum, diy_fp_bignum;
  bignum_assign_decimal_string(&buffer_bignum, buffer, buffer_len);
  bignum_assign_uint64(&diy_fp_bignum, diy_fp.f);
  if (exponent >= 0) {
    bignum_multiply_by_power_of_ten(&buffer_bignum, exponent);
  } else {
    bignum_multiply_by_power_of_ten(&diy_fp_bignum, -exponent);
  }
  if (diy_fp.e > 0) {
    bignum_shift_left(&diy_fp_bignum, diy_fp.e);
  } else {
    bignum_shift_left(&buffer_bignum, -diy_fp.e);
  }
  return bignum_compare(&buffer_bignum, &diy_fp_bignum);
}

static int strtod_compute_guess(const char *trimmed, int trimmed_len, int exponent, double *guess) {
  if (trimmed_len == 0) {
    *guess = 0.0;
    return 1;
  }
  if (exponent + trimmed_len - 1 >= STRTOD_MAX_DECIMAL_POWER) {
    *guess = dbl_infinity();
    return 1;
  }
  if (exponent + trimmed_len <= STRTOD_MIN_DECIMAL_POWER) {
    *guess = 0.0;
    return 1;
  }
  if (strtod_double_strtod(trimmed, trimmed_len, exponent, guess) ||
      strtod_diy_fp_strtod(trimmed, trimmed_len, exponent, guess)) {
    return 1;
  }
  if (*guess == dbl_infinity()) return 1;
  return 0;
}

static double strtod_trimmed(const char *trimmed, int trimmed_len, int exponent) {
  DC_ASSERT(trimmed_len <= STRTOD_MAX_SIGNIFICANT_DECIMAL_DIGITS);
  double guess;
  const int is_correct = strtod_compute_guess(trimmed, trimmed_len, exponent, &guess);
  if (is_correct) return guess;
  uint64_t guess64 = double_to_uint64(guess);
  DiyFp upper_boundary = dbl_upper_boundary(guess64);
  int comparison = strtod_compare_buffer_with_diy_fp(trimmed, trimmed_len, exponent, upper_boundary);
  if (comparison < 0) {
    return guess;
  } else if (comparison > 0) {
    return dbl_next_double(guess64);
  } else if ((dbl_significand(guess64) & 1) == 0) {
    return guess;
  } else {
    return dbl_next_double(guess64);
  }
}

static double strtod_impl(const char *buffer, int buffer_len, int exponent) {
  char copy_buffer[STRTOD_MAX_SIGNIFICANT_DECIMAL_DIGITS];
  const char *trimmed;
  int trimmed_len;
  int updated_exponent;
  strtod_trim_and_cut(buffer, buffer_len, exponent, copy_buffer, STRTOD_MAX_SIGNIFICANT_DECIMAL_DIGITS,
                       &trimmed, &trimmed_len, &updated_exponent);
  return strtod_trimmed(trimmed, trimmed_len, updated_exponent);
}

/* ============================================================
 * string-to-double.h / .cc  (double only, byte/char strings)
 * ============================================================ */

enum {
  STD_NO_FLAGS = 0,
  STD_ALLOW_HEX = 1,
  STD_ALLOW_OCTALS = 2,
  STD_ALLOW_TRAILING_JUNK = 4,
  STD_ALLOW_LEADING_SPACES = 8,
  STD_ALLOW_TRAILING_SPACES = 16,
  STD_ALLOW_SPACES_AFTER_SIGN = 32,
  STD_ALLOW_CASE_INSENSITIVITY = 64,
  STD_ALLOW_HEX_FLOATS = 128
};

#define STD_MAX_SIGNIFICANT_DIGITS 772

static const char kWhitespaceTable7[] = { 32, 13, 10, 9, 11, 12 };
#define STD_WHITESPACE7_LEN ((int)(sizeof(kWhitespaceTable7)/sizeof(kWhitespaceTable7[0])))
static const int kWhitespaceTable16[] = {
  160, 8232, 8233, 5760, 6158, 8192, 8193, 8194, 8195,
  8196, 8197, 8198, 8199, 8200, 8201, 8202, 8239, 8287, 12288, 65279
};
#define STD_WHITESPACE16_LEN ((int)(sizeof(kWhitespaceTable16)/sizeof(kWhitespaceTable16[0])))

static int std_is_whitespace(int x) {
  if (x < 128) {
    for (int i = 0; i < STD_WHITESPACE7_LEN; i++) if (kWhitespaceTable7[i] == x) return 1;
  } else {
    for (int i = 0; i < STD_WHITESPACE16_LEN; i++) if (kWhitespaceTable16[i] == x) return 1;
  }
  return 0;
}

/* Returns true if a nonspace found and false if the end has reached. */
static int std_advance_to_nonspace(const char **current, const char *end) {
  while (*current != end) {
    if (!std_is_whitespace(**current)) return 1;
    ++*current;
  }
  return 0;
}

static int std_is_digit(int x, int radix) {
  return (x >= '0' && x <= '9' && x < '0' + radix)
      || (radix > 10 && x >= 'a' && x < 'a' + radix - 10)
      || (radix > 10 && x >= 'A' && x < 'A' + radix - 10);
}

static double std_signed_zero(int sign) { return sign ? -0.0 : 0.0; }

static int std_is_decimal_digit_for_radix(int c, int radix) {
  return '0' <= c && c <= '9' && (c - '0') < radix;
}

static int std_is_character_digit_for_radix(int c, int radix, char a_character) {
  return radix > 10 && c >= a_character && c < a_character + radix - 10;
}

/* Returns true when the iterator is equal to end. */
static int std_advance(const char **it, char separator, int base, const char *end) {
  const char kNoSeparator = '\0';
  if (separator == kNoSeparator) {
    ++(*it);
    return *it == end;
  }
  if (!std_is_digit((unsigned char)**it, base)) {
    ++(*it);
    return *it == end;
  }
  ++(*it);
  if (*it == end) return 1;
  if (*it + 1 == end) return 0;
  if (**it == separator && std_is_digit((unsigned char)*(*it + 1), base)) {
    ++(*it);
  }
  return *it == end;
}

static char std_to_lower_ascii(char ch) {
  if (ch >= 'A' && ch <= 'Z') return (char)(ch + ('a' - 'A'));
  return ch;
}

static int std_consume_substring(const char **current, const char *end, const char *substring,
                                  int allow_case_insensitivity) {
  DC_ASSERT((allow_case_insensitivity ? std_to_lower_ascii(**current) : **current) == *substring);
  for (substring++; *substring != '\0'; substring++) {
    ++*current;
    char c = (*current == end) ? '\0' : **current;
    if (*current == end || (allow_case_insensitivity ? std_to_lower_ascii(c) : c) != *substring) {
      return 0;
    }
  }
  ++*current;
  return 1;
}

static int std_consume_first_character(char ch, const char *str, int case_insensitivity) {
  return case_insensitivity ? std_to_lower_ascii(ch) == str[0] : ch == str[0];
}

/* Generic radix parser (radix_log_2 in {3,4} used: octal=3, hex=4). */
static double std_radix_string_to_ieee(const char **current, const char *end, int sign,
                                        char separator, int parse_as_hex_float,
                                        int allow_trailing_junk, double junk_string_value,
                                        int radix_log_2, int *result_is_junk) {
  DC_ASSERT(*current != end);
  const int kSignificandSize = DBL_SIGNIFICAND_SIZE;
  *result_is_junk = 1;

  int64_t number = 0;
  int exponent = 0;
  const int radix = (1 << radix_log_2);
  int post_decimal = 0;

  while (**current == '0') {
    if (std_advance(current, separator, radix, end)) {
      *result_is_junk = 0;
      return std_signed_zero(sign);
    }
  }

  for (;;) {
    int digit;
    if (std_is_decimal_digit_for_radix((unsigned char)**current, radix)) {
      digit = (unsigned char)**current - '0';
      if (post_decimal) exponent -= radix_log_2;
    } else if (std_is_character_digit_for_radix((unsigned char)**current, radix, 'a')) {
      digit = (unsigned char)**current - 'a' + 10;
      if (post_decimal) exponent -= radix_log_2;
    } else if (std_is_character_digit_for_radix((unsigned char)**current, radix, 'A')) {
      digit = (unsigned char)**current - 'A' + 10;
      if (post_decimal) exponent -= radix_log_2;
    } else if (parse_as_hex_float && **current == '.') {
      post_decimal = 1;
      std_advance(current, separator, radix, end);
      DC_ASSERT(*current != end);
      continue;
    } else if (parse_as_hex_float && (**current == 'p' || **current == 'P')) {
      break;
    } else {
      if (allow_trailing_junk || !std_advance_to_nonspace(current, end)) {
        break;
      } else {
        return junk_string_value;
      }
    }

    number = number * radix + digit;
    int overflow = (int)(number >> kSignificandSize);
    if (overflow != 0) {
      int overflow_bits_count = 1;
      while (overflow > 1) {
        overflow_bits_count++;
        overflow >>= 1;
      }
      int dropped_bits_mask = ((1 << overflow_bits_count) - 1);
      int dropped_bits = (int)number & dropped_bits_mask;
      number >>= overflow_bits_count;
      exponent += overflow_bits_count;

      int zero_tail = 1;
      for (;;) {
        if (std_advance(current, separator, radix, end)) break;
        if (parse_as_hex_float && **current == '.') {
          std_advance(current, separator, radix, end);
          DC_ASSERT(*current != end);
          post_decimal = 1;
        }
        if (!std_is_digit((unsigned char)**current, radix)) break;
        zero_tail = zero_tail && **current == '0';
        if (!post_decimal) exponent += radix_log_2;
      }

      if (!parse_as_hex_float && !allow_trailing_junk && std_advance_to_nonspace(current, end)) {
        return junk_string_value;
      }

      int middle_value = (1 << (overflow_bits_count - 1));
      if (dropped_bits > middle_value) {
        number++;
      } else if (dropped_bits == middle_value) {
        if ((number & 1) != 0 || !zero_tail) number++;
      }

      if ((number & ((int64_t)1 << kSignificandSize)) != 0) {
        exponent++;
        number >>= 1;
      }
      break;
    }
    if (std_advance(current, separator, radix, end)) break;
  }

  DC_ASSERT(number < ((int64_t)1 << kSignificandSize));
  *result_is_junk = 0;

  if (parse_as_hex_float) {
    DC_ASSERT(**current == 'p' || **current == 'P');
    std_advance(current, separator, radix, end);
    DC_ASSERT(*current != end);
    int is_negative = 0;
    if (**current == '+') {
      std_advance(current, separator, radix, end);
      DC_ASSERT(*current != end);
    } else if (**current == '-') {
      is_negative = 1;
      std_advance(current, separator, radix, end);
      DC_ASSERT(*current != end);
    }
    int written_exponent = 0;
    while (std_is_decimal_digit_for_radix((unsigned char)**current, 10)) {
      if (abs(written_exponent) <= 100 * DBL_MAX_EXPONENT) {
        written_exponent = 10 * written_exponent + **current - '0';
      }
      if (std_advance(current, separator, radix, end)) break;
    }
    if (is_negative) written_exponent = -written_exponent;
    exponent += written_exponent;
  }

  if (exponent == 0 || number == 0) {
    if (sign) {
      if (number == 0) return -0.0;
      number = -number;
    }
    return (double)number;
  }

  DC_ASSERT(number != 0);
  double result = dbl_value(double_to_uint64(0));
  {
    DiyFp fp = diyfp_make((uint64_t)number, exponent);
    /* Double(DiyFp) construction, mirroring DiyFpToUint64 */
    uint64_t significand = fp.f;
    int exp = fp.e;
    while (significand > DBL_HIDDEN_BIT + DBL_SIGNIFICAND_MASK) {
      significand >>= 1;
      exp++;
    }
    uint64_t bits;
    if (exp >= DBL_MAX_EXPONENT) {
      bits = DBL_INFINITY_BITS;
    } else if (exp < DBL_DENORMAL_EXPONENT) {
      bits = 0;
    } else {
      while (exp > DBL_DENORMAL_EXPONENT && (significand & DBL_HIDDEN_BIT) == 0) {
        significand <<= 1;
        exp--;
      }
      uint64_t biased_exponent;
      if (exp == DBL_DENORMAL_EXPONENT && (significand & DBL_HIDDEN_BIT) == 0) {
        biased_exponent = 0;
      } else {
        biased_exponent = (uint64_t)(exp + DBL_EXPONENT_BIAS);
      }
      bits = (significand & DBL_SIGNIFICAND_MASK) | (biased_exponent << DBL_PHYSICAL_SIGNIFICAND_SIZE);
    }
    result = dbl_value(bits);
  }
  return sign ? -result : result;
}

static double std_string_to_ieee(int flags, double empty_string_value, double junk_string_value,
                                  const char *infinity_symbol, const char *nan_symbol,
                                  char separator,
                                  const char *input, int length, int *processed_characters_count) {
  const char *current = input;
  const char *end = input + length;

  *processed_characters_count = 0;

  const int allow_trailing_junk = (flags & STD_ALLOW_TRAILING_JUNK) != 0;
  const int allow_leading_spaces = (flags & STD_ALLOW_LEADING_SPACES) != 0;
  const int allow_trailing_spaces = (flags & STD_ALLOW_TRAILING_SPACES) != 0;
  const int allow_spaces_after_sign = (flags & STD_ALLOW_SPACES_AFTER_SIGN) != 0;
  const int allow_case_insensitivity = (flags & STD_ALLOW_CASE_INSENSITIVITY) != 0;

  if (current == end) return empty_string_value;

  if (allow_leading_spaces || allow_trailing_spaces) {
    if (!std_advance_to_nonspace(&current, end)) {
      *processed_characters_count = (int)(current - input);
      return empty_string_value;
    }
    if (!allow_leading_spaces && (input != current)) {
      return junk_string_value;
    }
  }

  int exponent = 0;
  int significant_digits = 0;
  int insignificant_digits = 0;
  int nonzero_digit_dropped = 0;
  int sign = 0;

  if (*current == '+' || *current == '-') {
    sign = (*current == '-');
    ++current;
    const char *next_non_space = current;
    if (!std_advance_to_nonspace(&next_non_space, end)) return junk_string_value;
    if (!allow_spaces_after_sign && (current != next_non_space)) {
      return junk_string_value;
    }
    current = next_non_space;
  }

  if (infinity_symbol != NULL) {
    if (std_consume_first_character(*current, infinity_symbol, allow_case_insensitivity)) {
      if (!std_consume_substring(&current, end, infinity_symbol, allow_case_insensitivity)) {
        return junk_string_value;
      }
      if (!(allow_trailing_spaces || allow_trailing_junk) && (current != end)) {
        return junk_string_value;
      }
      if (!allow_trailing_junk && std_advance_to_nonspace(&current, end)) {
        return junk_string_value;
      }
      *processed_characters_count = (int)(current - input);
      return sign ? -dbl_infinity() : dbl_infinity();
    }
  }

  if (nan_symbol != NULL) {
    if (std_consume_first_character(*current, nan_symbol, allow_case_insensitivity)) {
      if (!std_consume_substring(&current, end, nan_symbol, allow_case_insensitivity)) {
        return junk_string_value;
      }
      if (!(allow_trailing_spaces || allow_trailing_junk) && (current != end)) {
        return junk_string_value;
      }
      if (!allow_trailing_junk && std_advance_to_nonspace(&current, end)) {
        return junk_string_value;
      }
      *processed_characters_count = (int)(current - input);
      return sign ? -dbl_nan() : dbl_nan();
    }
  }

  int leading_zero = 0;
  if (*current == '0') {
    if (std_advance(&current, separator, 10, end)) {
      *processed_characters_count = (int)(current - input);
      return std_signed_zero(sign);
    }
    leading_zero = 1;

    if (((flags & STD_ALLOW_HEX) || (flags & STD_ALLOW_HEX_FLOATS)) &&
        (*current == 'x' || *current == 'X')) {
      ++current;
      if (current == end) return junk_string_value;

      /* ALLOW_HEX_FLOATS not used by our converters; parse_as_hex_float stays 0
         unless that flag is set (kept for fidelity though unused). */
      int parse_as_hex_float = 0;
      if ((flags & STD_ALLOW_HEX_FLOATS) != 0) {
        /* Hex-float detection omitted (not exercised by ant's converters);
           if ever enabled this would call IsHexFloatString. */
        parse_as_hex_float = 0;
      }

      if (!parse_as_hex_float && !std_is_digit((unsigned char)*current, 16)) {
        return junk_string_value;
      }

      int result_is_junk;
      double result = std_radix_string_to_ieee(&current, end, sign, separator,
                                                parse_as_hex_float, allow_trailing_junk,
                                                junk_string_value, 4, &result_is_junk);
      if (!result_is_junk) {
        if (allow_trailing_spaces) std_advance_to_nonspace(&current, end);
        *processed_characters_count = (int)(current - input);
      }
      return result;
    }

    while (*current == '0') {
      if (std_advance(&current, separator, 10, end)) {
        *processed_characters_count = (int)(current - input);
        return std_signed_zero(sign);
      }
    }
  }

  int octal = leading_zero && (flags & STD_ALLOW_OCTALS) != 0;

  const int kBufferSize = STD_MAX_SIGNIFICANT_DIGITS + 10;
  char buffer[STD_MAX_SIGNIFICANT_DIGITS + 10];
  int buffer_pos = 0;

  while (*current >= '0' && *current <= '9') {
    if (significant_digits < STD_MAX_SIGNIFICANT_DIGITS) {
      DC_ASSERT(buffer_pos < kBufferSize);
      buffer[buffer_pos++] = *current;
      significant_digits++;
    } else {
      insignificant_digits++;
      nonzero_digit_dropped = nonzero_digit_dropped || *current != '0';
    }
    octal = octal && *current < '8';
    if (std_advance(&current, separator, 10, end)) goto parsing_done;
  }

  if (significant_digits == 0) octal = 0;

  if (*current == '.') {
    if (octal && !allow_trailing_junk) return junk_string_value;
    if (octal) goto parsing_done;

    if (std_advance(&current, separator, 10, end)) {
      if (significant_digits == 0 && !leading_zero) {
        return junk_string_value;
      } else {
        goto parsing_done;
      }
    }

    if (significant_digits == 0) {
      while (*current == '0') {
        if (std_advance(&current, separator, 10, end)) {
          *processed_characters_count = (int)(current - input);
          return std_signed_zero(sign);
        }
        exponent--;
      }
    }

    while (*current >= '0' && *current <= '9') {
      if (significant_digits < STD_MAX_SIGNIFICANT_DIGITS) {
        DC_ASSERT(buffer_pos < kBufferSize);
        buffer[buffer_pos++] = *current;
        significant_digits++;
        exponent--;
      } else {
        nonzero_digit_dropped = nonzero_digit_dropped || *current != '0';
      }
      if (std_advance(&current, separator, 10, end)) goto parsing_done;
    }
  }

  if (!leading_zero && exponent == 0 && significant_digits == 0) {
    return junk_string_value;
  }

  if (*current == 'e' || *current == 'E') {
    if (octal && !allow_trailing_junk) return junk_string_value;
    if (octal) goto parsing_done;
    const char *junk_begin = current;
    ++current;
    if (current == end) {
      if (allow_trailing_junk) {
        current = junk_begin;
        goto parsing_done;
      } else {
        return junk_string_value;
      }
    }
    char exponen_sign = '+';
    if (*current == '+' || *current == '-') {
      exponen_sign = *current;
      ++current;
      if (current == end) {
        if (allow_trailing_junk) {
          current = junk_begin;
          goto parsing_done;
        } else {
          return junk_string_value;
        }
      }
    }

    if (current == end || *current < '0' || *current > '9') {
      if (allow_trailing_junk) {
        current = junk_begin;
        goto parsing_done;
      } else {
        return junk_string_value;
      }
    }

    const int max_exponent = INT_MAX / 2;
    int num = 0;
    do {
      int digit = *current - '0';
      if (num >= max_exponent / 10 && !(num == max_exponent / 10 && digit <= max_exponent % 10)) {
        num = max_exponent;
      } else {
        num = num * 10 + digit;
      }
      ++current;
    } while (current != end && *current >= '0' && *current <= '9');

    exponent += (exponen_sign == '-' ? -num : num);
  }

  if (!(allow_trailing_spaces || allow_trailing_junk) && (current != end)) {
    return junk_string_value;
  }
  if (!allow_trailing_junk && std_advance_to_nonspace(&current, end)) {
    return junk_string_value;
  }
  if (allow_trailing_spaces) {
    std_advance_to_nonspace(&current, end);
  }

parsing_done:
  exponent += insignificant_digits;

  if (octal) {
    double result;
    int result_is_junk;
    const char *start = buffer;
    result = std_radix_string_to_ieee(&start, buffer + buffer_pos, sign, separator,
                                      0, allow_trailing_junk, junk_string_value, 3, &result_is_junk);
    DC_ASSERT(!result_is_junk);
    *processed_characters_count = (int)(current - input);
    return result;
  }

  if (nonzero_digit_dropped) {
    buffer[buffer_pos++] = '1';
    exponent--;
  }

  DC_ASSERT(buffer_pos < kBufferSize);
  buffer[buffer_pos] = '\0';

  int chars_len = buffer_pos;
  int trimmed_len = strtod_trim_trailing_zeros_len(buffer, chars_len);
  exponent += buffer_pos - trimmed_len;

  double converted = strtod_trimmed(buffer, trimmed_len, exponent);
  *processed_characters_count = (int)(current - input);
  return sign ? -converted : converted;
}

/* Wrapper matching the three converter configurations used by ant. */
static double std_string_to_double(int flags, const char *buffer, int length,
                                    int *processed_characters_count) {
  return std_string_to_ieee(flags, 0.0, dbl_nan(), "Infinity", "NaN", '\0',
                             buffer, length, processed_characters_count);
}

/* ============================================================
 * Top-level JS-facing wrapper (verbatim port of src/numbers.cc)
 * ============================================================ */

#define kMaxCharsEcmaScriptShortest 25
#define kMaxFixedDigitsBeforePoint 60
#define kMaxFixedDigitsAfterPoint 100
#define kMaxPrecisionDigits 120
#define kMaxExponentialDigits 120

static const size_t kShortestBufferSize = kMaxCharsEcmaScriptShortest + 1;
static const size_t kFixedBufferSize =
  1 + kMaxFixedDigitsBeforePoint + 1 + kMaxFixedDigitsAfterPoint + 1;
static const size_t kPrecisionBufferSize = kMaxPrecisionDigits + 7 + 1;
static const size_t kExponentialBufferSize = kMaxExponentialDigits + 8 + 1;

typedef struct {
  const char *bytes;
  size_t len;
} JsTrimToken;

#define JS_TRIM_TOKEN(bytes) { bytes, sizeof(bytes) - 1 }
static const JsTrimToken kJsStringTrimTokens[] = {
  JS_TRIM_TOKEN("\xc2""\xa0"),
  JS_TRIM_TOKEN("\xe1""\x9a""\x80"),
  JS_TRIM_TOKEN("\xe2""\x80""\x80"),
  JS_TRIM_TOKEN("\xe2""\x80""\x81"),
  JS_TRIM_TOKEN("\xe2""\x80""\x82"),
  JS_TRIM_TOKEN("\xe2""\x80""\x83"),
  JS_TRIM_TOKEN("\xe2""\x80""\x84"),
  JS_TRIM_TOKEN("\xe2""\x80""\x85"),
  JS_TRIM_TOKEN("\xe2""\x80""\x86"),
  JS_TRIM_TOKEN("\xe2""\x80""\x87"),
  JS_TRIM_TOKEN("\xe2""\x80""\x88"),
  JS_TRIM_TOKEN("\xe2""\x80""\x89"),
  JS_TRIM_TOKEN("\xe2""\x80""\x8a"),
  JS_TRIM_TOKEN("\xe2""\x80""\xa8"),
  JS_TRIM_TOKEN("\xe2""\x80""\xa9"),
  JS_TRIM_TOKEN("\xe2""\x80""\xaf"),
  JS_TRIM_TOKEN("\xe2""\x81""\x9f"),
  JS_TRIM_TOKEN("\xe3""\x80""\x80"),
  JS_TRIM_TOKEN("\xef""\xbb""\xbf"),
};
#undef JS_TRIM_TOKEN
#define kJsStringTrimTokensCount ((int)(sizeof(kJsStringTrimTokens)/sizeof(kJsStringTrimTokens[0])))

static int is_ascii_js_string_trim_byte(unsigned char ch) {
  return
    ch == ' ' || ch == '\t' || ch == '\n' ||
    ch == '\v' || ch == '\f' || ch == '\r';
}

static size_t js_string_trim_prefix_len(const char *str, size_t len) {
  if (len == 0) return 0;

  unsigned char first = (unsigned char)str[0];
  if (first < 0x80) return is_ascii_js_string_trim_byte(first) ? 1 : 0;

  for (int i = 0; i < kJsStringTrimTokensCount; i++) {
    const JsTrimToken *token = &kJsStringTrimTokens[i];
    if (len >= token->len && memcmp(str, token->bytes, token->len) == 0) return token->len;
  }
  return 0;
}

static size_t js_string_trim_suffix_len(const char *str, size_t len) {
  if (len == 0) return 0;

  unsigned char last = (unsigned char)str[len - 1];
  if (last < 0x80) return is_ascii_js_string_trim_byte(last) ? 1 : 0;

  for (int i = 0; i < kJsStringTrimTokensCount; i++) {
    const JsTrimToken *token = &kJsStringTrimTokens[i];
    if (len >= token->len && memcmp(str + len - token->len, token->bytes, token->len) == 0) return token->len;
  }
  return 0;
}

static void trim_js_string_whitespace(const char **str, size_t *len, int trim_trailing, size_t *leading) {
  size_t lead = 0;

  while (*len > 0) {
    size_t n = js_string_trim_prefix_len(*str, *len);
    if (n == 0) break;
    *str += n; *len -= n; lead += n;
  }

  while (trim_trailing && *len > 0) {
    size_t n = js_string_trim_suffix_len(*str, *len);
    if (n == 0) break;
    *len -= n;
  }

  if (leading) *leading = lead;
}

static int ant_starts_with_nondecimal_prefix(const char *str, size_t len) {
  return
    len >= 2 && str[0] == '0' &&
    ((str[1] | 0x20) == 'x' ||
    (str[1] | 0x20)  == 'b' || (str[1] | 0x20) == 'o');
}

static int ant_parse_radix_integer(const char *str, size_t len, int radix, double *out) {
  if (!str || len == 0 || !out) return 0;
  double value = 0.0;

  for (size_t i = 0; i < len; i++) {
    unsigned char ch = (unsigned char)str[i];
    int digit = -1;
    if (ch >= '0' && ch <= '9') digit = ch - '0';
    else if (ch >= 'a' && ch <= 'z') digit = ch - 'a' + 10;
    else if (ch >= 'A' && ch <= 'Z') digit = ch - 'A' + 10;
    if (digit < 0 || digit >= radix) return 0;
    value = value * (double)radix + (double)digit;
  }

  *out = value;
  return 1;
}

static int ant_parse_js_number_prefix(const char *str, size_t len, double *out) {
  if (len < 3 || str[0] != '0') return 0;

  char kind = (char)(str[1] | 0x20);
  int radix = kind == 'b' ? 2 : (kind == 'o' ? 8 : 0);
  if (radix == 0) return 0;

  double value = 0.0;
  if (!ant_parse_radix_integer(str + 2, len - 2, radix, &value))
    return 0;

  *out = value;
  return 1;
}

bool ant_number_parse(
  const char *str, size_t len,
  ant_number_parse_mode_t mode,
  double *out, size_t *processed
) {
  if (processed) *processed = 0;
  if (!str || !out) return false;

  size_t leading = 0;
  if (mode == ANT_NUMBER_PARSE_JS_NUMBER || mode == ANT_NUMBER_PARSE_FLOAT_PREFIX) {
    trim_js_string_whitespace(&str, &len, mode == ANT_NUMBER_PARSE_JS_NUMBER, &leading);

    if (mode == ANT_NUMBER_PARSE_JS_NUMBER && len == 0) {
      *out = 0.0;
      if (processed) *processed = leading;
      return true;
    }
  }

  if (
    mode == ANT_NUMBER_PARSE_JS_NUMBER && len >= 3 &&
    (str[0] == '+' || str[0] == '-') &&
    ant_starts_with_nondecimal_prefix(str + 1, len - 1)
  ) return false;

  if (mode == ANT_NUMBER_PARSE_JS_NUMBER && ant_parse_js_number_prefix(str, len, out)) {
    if (processed) *processed = len;
    return true;
  }

  int converter_flags = STD_NO_FLAGS;
  if (mode == ANT_NUMBER_PARSE_JS_NUMBER) converter_flags = STD_ALLOW_HEX;
  else if (mode == ANT_NUMBER_PARSE_FLOAT_PREFIX) converter_flags = STD_ALLOW_TRAILING_JUNK;

  int count = 0;
  double value = std_string_to_double(converter_flags, str, (int)len, &count);

  if (count <= 0) return false;
  if (mode != ANT_NUMBER_PARSE_FLOAT_PREFIX && (size_t)count != len) return false;

  *out = value;
  if (processed) *processed = leading + (size_t)count;

  return true;
}

static inline size_t copy_truncated_number_result(char *dst, size_t dstlen, const char *src, size_t srclen) {
  if (!dst || dstlen == 0) return srclen;
  size_t n = srclen < dstlen - 1 ? srclen : dstlen - 1;

  if (n > 0) memcpy(dst, src, n);
  dst[n] = '\0';

  return srclen;
}

size_t ant_number_to_shortest(double value, char *buf, size_t len) {
  char scratch[kShortestBufferSize];
  char *out = (buf && len >= sizeof(scratch)) ? buf : scratch;
  size_t out_len = (out == buf) ? len : sizeof(scratch);

  StringBuilder builder;
  sb_init(&builder, out, (int)out_len);
  int ok = dts_to_shortest(value, &builder);
  if (!ok) return 0;

  int pos = sb_position(&builder);
  if (pos < 0) return 0;
  sb_finalize(&builder);

  if (out == buf) return (size_t)pos;
  return copy_truncated_number_result(buf, len, scratch, (size_t)pos);
}

size_t ant_number_to_fixed(double value, int digits, char *buf, size_t len) {
  char scratch[kFixedBufferSize];
  char *out = (buf && len >= sizeof(scratch)) ? buf : scratch;
  size_t out_len = (out == buf) ? len : sizeof(scratch);

  StringBuilder builder;
  sb_init(&builder, out, (int)out_len);
  int ok = dts_to_fixed(value, digits, &builder);
  if (!ok) return 0;

  int pos = sb_position(&builder);
  if (pos < 0) return 0;
  sb_finalize(&builder);

  if (out == buf) return (size_t)pos;
  return copy_truncated_number_result(buf, len, scratch, (size_t)pos);
}

size_t ant_number_to_precision(double value, int precision, char *buf, size_t len) {
  char scratch[kPrecisionBufferSize];
  char *out = (buf && len >= sizeof(scratch)) ? buf : scratch;
  size_t out_len = (out == buf) ? len : sizeof(scratch);

  StringBuilder builder;
  sb_init(&builder, out, (int)out_len);
  int ok = dts_to_precision(value, precision, &builder);
  if (!ok) return 0;

  int pos = sb_position(&builder);
  if (pos < 0) return 0;
  sb_finalize(&builder);

  if (out == buf) return (size_t)pos;
  return copy_truncated_number_result(buf, len, scratch, (size_t)pos);
}

size_t ant_number_to_exponential(double value, int digits, char *buf, size_t len) {
  char scratch[kExponentialBufferSize];
  char *out = (buf && len >= sizeof(scratch)) ? buf : scratch;
  size_t out_len = (out == buf) ? len : sizeof(scratch);

  StringBuilder builder;
  sb_init(&builder, out, (int)out_len);
  int ok = dts_to_exponential(value, digits, &builder);
  if (!ok) return 0;

  int pos = sb_position(&builder);
  if (pos < 0) return 0;
  sb_finalize(&builder);

  if (out == buf) return (size_t)pos;
  return copy_truncated_number_result(buf, len, scratch, (size_t)pos);
}
