//! Elementary number theory on `u64`: primality and factorisation.

use crate::infra::zmod::gcd;

/// `a b mod n` without overflow.
fn mulmod(a: u64, b: u64, n: u64) -> u64 {
    u64::try_from(u128::from(a) * u128::from(b) % u128::from(n)).expect("residue fits")
}

fn powmod(mut a: u64, mut e: u64, n: u64) -> u64 {
    let mut r = 1 % n;
    a %= n;
    while e > 0 {
        if e & 1 == 1 {
            r = mulmod(r, a, n);
        }
        a = mulmod(a, a, n);
        e >>= 1;
    }
    r
}

/// Miller--Rabin bases that are deterministic for every `n < 2^64`.
const MR_BASES: [u64; 12] = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37];

/// Deterministic primality test.
pub fn is_prime(n: u64) -> bool {
    if n < 2 {
        return false;
    }
    for p in MR_BASES {
        if n.is_multiple_of(p) {
            return n == p;
        }
    }
    let (mut d, mut s) = (n - 1, 0u32);
    while d % 2 == 0 {
        d /= 2;
        s += 1;
    }
    'bases: for a in MR_BASES {
        let mut x = powmod(a, d, n);
        if x == 1 || x == n - 1 {
            continue;
        }
        for _ in 1..s {
            x = mulmod(x, x, n);
            if x == n - 1 {
                continue 'bases;
            }
        }
        return false;
    }
    true
}

/// A nontrivial factor of the odd composite `n` (Pollard's rho, Floyd cycle finding).
fn find_factor(n: u64) -> u64 {
    let mut c = 1u64;
    loop {
        let f = |x: u64| (mulmod(x, x, n) + c) % n;
        let (mut x, mut y, mut d) = (2u64, 2u64, 1u64);
        while d == 1 {
            x = f(x);
            y = f(f(y));
            d = gcd(x.abs_diff(y), n);
        }
        if d != n {
            return d;
        }
        c += 1;
    }
}

/// The factorisation of `n >= 1` as `(prime, exponent)` pairs in increasing order.
pub fn factor(mut n: u64) -> Vec<(u64, u32)> {
    assert!(n >= 1, "factor of 0");
    let mut primes: Vec<u64> = Vec::new();
    for p in [2u64, 3, 5] {
        while n.is_multiple_of(p) {
            primes.push(p);
            n /= p;
        }
    }
    let mut stack = if n > 1 { vec![n] } else { vec![] };
    while let Some(m) = stack.pop() {
        if is_prime(m) {
            primes.push(m);
        } else {
            let d = find_factor(m);
            stack.push(d);
            stack.push(m / d);
        }
    }
    primes.sort_unstable();
    let mut result: Vec<(u64, u32)> = Vec::new();
    for p in primes {
        match result.last_mut() {
            Some((q, k)) if *q == p => *k += 1,
            _ => result.push((p, 1)),
        }
    }
    result
}

/// Euler's totient of `m >= 1`, exactly.
pub fn euler_phi(m: u64) -> u64 {
    factor(m).iter().fold(m, |acc, &(p, _)| acc / p * (p - 1))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn small_factorisations() {
        for n in 1..2000u64 {
            let f = factor(n);
            assert_eq!(f.iter().map(|&(p, k)| p.pow(k)).product::<u64>(), n);
            assert!(f.iter().all(|&(p, _)| is_prime(p)));
        }
    }

    #[test]
    fn large_numbers() {
        let p = (1u64 << 61) - 1;
        assert!(is_prime(p));
        assert_eq!(factor(p), vec![(p, 1)]);
        let n = 4_294_967_291u64 * 4_294_967_279u64;
        assert_eq!(factor(n), vec![(4_294_967_279, 1), (4_294_967_291, 1)]);
        assert_eq!(euler_phi(36), 12);
    }
}
