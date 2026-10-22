//! Arithmetic modulo `m`, for `1 <= m < 2^63`. Residues are `u64` in `[0, m)`;
//! products go through `u128` followed by `% m`.

/// A modulus `1 <= m < 2^63`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Modulus {
    m: u64,
}

impl Modulus {
    /// The modulus `m`; panics unless `1 <= m < 2^63` (callers validate first).
    pub fn new(m: u64) -> Modulus {
        assert!((1..1u64 << 63).contains(&m), "modulus out of range");
        Modulus { m }
    }

    /// The value of the modulus.
    pub fn value(&self) -> u64 {
        self.m
    }

    /// `x mod m` for any `x`.
    pub fn reduce_i128(&self, x: i128) -> u64 {
        u64::try_from(x.rem_euclid(i128::from(self.m))).expect("residue fits")
    }

    /// `x mod m` for any `x`.
    pub fn reduce_u64(&self, x: u64) -> u64 {
        x % self.m
    }

    /// `1 mod m` (which is 0 when m = 1).
    pub fn one(&self) -> u64 {
        1 % self.m
    }

    /// `a + b mod m` for residues `a, b`.
    pub fn add(&self, a: u64, b: u64) -> u64 {
        let s = a + b; // a, b < 2^63, no overflow
        if s >= self.m { s - self.m } else { s }
    }

    /// `a - b mod m` for residues `a, b`.
    pub fn sub(&self, a: u64, b: u64) -> u64 {
        if a >= b { a - b } else { a + self.m - b }
    }

    /// `-a mod m` for a residue `a`.
    pub fn neg(&self, a: u64) -> u64 {
        if a == 0 { 0 } else { self.m - a }
    }

    /// `a b mod m` for residues `a, b`.
    pub fn mul(&self, a: u64, b: u64) -> u64 {
        u64::try_from(u128::from(a) * u128::from(b) % u128::from(self.m)).expect("residue fits")
    }

    /// Whether `a` is a unit (every residue is a unit modulo 1).
    pub fn is_unit(&self, a: u64) -> bool {
        gcd(a, self.m) == 1
    }

    /// The inverse of the residue `a`, if it is a unit.
    pub fn inv(&self, a: u64) -> Option<u64> {
        if self.m == 1 {
            return Some(0);
        }
        // Extended Euclid on (a, m), tracking only the coefficient of a.
        let (mut r0, mut r1) = (i128::from(self.m), i128::from(a));
        let (mut t0, mut t1) = (0i128, 1i128);
        while r1 != 0 {
            let q = r0 / r1;
            (r0, r1) = (r1, r0 - q * r1);
            (t0, t1) = (t1, t0 - q * t1);
        }
        if r0 == 1 {
            Some(self.reduce_i128(t0))
        } else {
            None
        }
    }
}

/// The greatest common divisor (gcd(0, 0) = 0).
pub fn gcd(mut a: u64, mut b: u64) -> u64 {
    while b != 0 {
        (a, b) = (b, a % b);
    }
    a
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn inverses() {
        for m in 1..60u64 {
            let md = Modulus::new(m);
            for a in 0..m {
                match md.inv(a) {
                    Some(b) => assert_eq!(md.mul(a, b), md.one(), "{a} mod {m}"),
                    None => assert!(!md.is_unit(a)),
                }
            }
        }
    }

    #[test]
    fn large_modulus() {
        let m = (1u64 << 63) - 25; // prime
        let md = Modulus::new(m);
        let a = m - 2;
        assert_eq!(md.mul(a, md.inv(a).unwrap()), 1);
        assert_eq!(md.add(m - 1, m - 1), m - 2);
        assert_eq!(md.reduce_i128(-1), m - 1);
    }
}
