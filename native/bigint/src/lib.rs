//! Arbitrary precision integers for arithkit.
//!
//! [`BigInt`] is a newtype over the backend's signed integer (currently
//! dashu's `IBig`; the choice is provisional). This crate is the only one that
//! depends on the backend, so swapping it only touches this file. Only the
//! operations arithkit needs are exposed, with the semantics documented here:
//!
//! - arithmetic (`+`, `-`, `*`) is exact;
//! - [`BigInt::div_exact`] divides only when the division is exact;
//! - [`BigInt::rem_euclid_u64`] is the remainder in `[0, m)` (Euclidean);
//! - hexadecimal conversion uses lower case digits, an optional leading `-`
//!   and no prefix, as Python's `format(x, "x")`;
//! - nothing panics on valid input; division by zero is reported as `None`.

use std::cmp::Ordering;
use std::fmt;
use std::ops::{Add, Mul, Neg, Sub};

use dashu_int::ops::{SquareRoot, UnsignedAbs};
use dashu_int::{IBig, UBig};

/// A signed integer of arbitrary size.
#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Default)]
pub struct BigInt(IBig);

impl BigInt {
    /// Zero.
    pub fn zero() -> BigInt {
        BigInt(IBig::ZERO)
    }

    /// Parses `-?[0-9a-f]+` (Python's `format(x, "x")`); `None` otherwise.
    pub fn from_hex(text: &str) -> Option<BigInt> {
        let (negative, digits) = match text.strip_prefix('-') {
            Some(rest) => (true, rest),
            None => (false, text),
        };
        if digits.is_empty()
            || !digits
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        {
            return None;
        }
        let magnitude = UBig::from_str_radix(digits, 16).ok()?;
        let value = IBig::from(magnitude);
        Some(BigInt(if negative { -value } else { value }))
    }

    /// The hexadecimal representation, as parsed by [`BigInt::from_hex`].
    pub fn to_hex(&self) -> String {
        let text = format!("{:x}", self.0.clone().unsigned_abs());
        if self.is_negative() {
            format!("-{text}")
        } else {
            text
        }
    }

    /// Whether the value is zero.
    pub fn is_zero(&self) -> bool {
        self.0 == IBig::ZERO
    }

    /// Whether the value is negative.
    pub fn is_negative(&self) -> bool {
        self.0 < IBig::ZERO
    }

    /// The sign: -1, 0 or 1.
    pub fn signum(&self) -> i32 {
        match self.0.cmp(&IBig::ZERO) {
            Ordering::Less => -1,
            Ordering::Equal => 0,
            Ordering::Greater => 1,
        }
    }

    /// `self / d` if `d` is nonzero and divides `self`, else `None`.
    pub fn div_exact(&self, d: &BigInt) -> Option<BigInt> {
        if d.is_zero() {
            return None;
        }
        let q = &self.0 / &d.0;
        if &q * &d.0 == self.0 {
            Some(BigInt(q))
        } else {
            None
        }
    }

    /// Whether `d` divides `self` (`d` nonzero).
    pub fn is_divisible_by(&self, d: &BigInt) -> bool {
        self.div_exact(d).is_some()
    }

    /// The remainder of `self` modulo `m >= 1`, in `[0, m)`.
    pub fn rem_euclid_u64(&self, m: u64) -> u64 {
        assert!(m >= 1, "modulus must be positive");
        let r = &self.0 % IBig::from(m);
        let r = if r < IBig::ZERO { r + IBig::from(m) } else { r };
        u64::try_from(r).expect("remainder lies in [0, m)")
    }

    /// The square root if `self` is a perfect square (in particular nonnegative).
    pub fn sqrt_exact(&self) -> Option<BigInt> {
        if self.is_negative() {
            return None;
        }
        let magnitude = self.0.clone().unsigned_abs();
        let root = magnitude.sqrt();
        if &root * &root == magnitude {
            Some(BigInt(IBig::from(root)))
        } else {
            None
        }
    }

    /// The remainder of `self` modulo `m >= 1`, in `[0, m)`.
    pub fn rem_euclid(&self, m: &BigInt) -> BigInt {
        assert!(m.signum() > 0, "modulus must be positive");
        let r = &self.0 % &m.0;
        BigInt(if r < IBig::ZERO { r + &m.0 } else { r })
    }

    /// `self^e`.
    pub fn pow(&self, e: u32) -> BigInt {
        (0..e).fold(BigInt::from(1u64), |acc, _| &acc * self)
    }

    /// The `p`-adic valuation for `p >= 2`; `None` for zero.
    pub fn valuation(&self, p: &BigInt) -> Option<u32> {
        if self.is_zero() {
            return None;
        }
        let (mut rest, mut v) = (self.clone(), 0u32);
        while let Some(q) = rest.div_exact(p) {
            rest = q;
            v += 1;
        }
        Some(v)
    }

    /// The value as a `u64`, if it fits.
    pub fn to_u64(&self) -> Option<u64> {
        u64::try_from(&self.0).ok()
    }

    /// The value as an `i64`, if it fits.
    pub fn to_i64(&self) -> Option<i64> {
        i64::try_from(&self.0).ok()
    }
}

impl From<i64> for BigInt {
    fn from(x: i64) -> BigInt {
        BigInt(IBig::from(x))
    }
}

impl From<u64> for BigInt {
    fn from(x: u64) -> BigInt {
        BigInt(IBig::from(x))
    }
}

impl From<i128> for BigInt {
    fn from(x: i128) -> BigInt {
        BigInt(IBig::from(x))
    }
}

impl fmt::Debug for BigInt {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl fmt::Display for BigInt {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl Add<&BigInt> for &BigInt {
    type Output = BigInt;
    fn add(self, rhs: &BigInt) -> BigInt {
        BigInt(&self.0 + &rhs.0)
    }
}

impl Sub<&BigInt> for &BigInt {
    type Output = BigInt;
    fn sub(self, rhs: &BigInt) -> BigInt {
        BigInt(&self.0 - &rhs.0)
    }
}

impl Mul<&BigInt> for &BigInt {
    type Output = BigInt;
    fn mul(self, rhs: &BigInt) -> BigInt {
        BigInt(&self.0 * &rhs.0)
    }
}

impl Neg for &BigInt {
    type Output = BigInt;
    fn neg(self) -> BigInt {
        BigInt(-&self.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hex_round_trip() {
        for text in ["0", "1", "-1", "ff", "-123456789abcdef0123456789abcdef"] {
            assert_eq!(BigInt::from_hex(text).unwrap().to_hex(), text);
        }
        for bad in ["", "-", "0x1", "G", "1 "] {
            assert!(BigInt::from_hex(bad).is_none(), "{bad}");
        }
    }

    #[test]
    fn euclidean_remainder() {
        assert_eq!(BigInt::from(-7i64).rem_euclid_u64(3), 2);
        assert_eq!(BigInt::from(7i64).rem_euclid_u64(3), 1);
        assert_eq!(BigInt::from(-6i64).rem_euclid_u64(3), 0);
        assert_eq!(BigInt::from(5i64).rem_euclid_u64(1), 0);
    }

    #[test]
    fn remainders_powers_valuations() {
        let seven = BigInt::from(7i64);
        assert_eq!(BigInt::from(-1i64).rem_euclid(&seven), BigInt::from(6i64));
        assert_eq!(BigInt::from(3i64).pow(4), BigInt::from(81i64));
        assert_eq!(BigInt::from(3i64).pow(0), BigInt::from(1i64));
        assert_eq!(
            BigInt::from(-162i64).valuation(&BigInt::from(3i64)),
            Some(4)
        );
        assert_eq!(BigInt::zero().valuation(&BigInt::from(3i64)), None);
    }

    #[test]
    fn exact_division_and_roots() {
        let a = BigInt::from(-12i64);
        assert_eq!(a.div_exact(&BigInt::from(4i64)), Some(BigInt::from(-3i64)));
        assert_eq!(a.div_exact(&BigInt::from(5i64)), None);
        assert_eq!(a.div_exact(&BigInt::zero()), None);
        assert_eq!(BigInt::from(49i64).sqrt_exact(), Some(BigInt::from(7i64)));
        assert_eq!(BigInt::from(50i64).sqrt_exact(), None);
        assert_eq!(BigInt::from(-4i64).sqrt_exact(), None);
        assert_eq!(BigInt::zero().sqrt_exact(), Some(BigInt::zero()));
    }
}
