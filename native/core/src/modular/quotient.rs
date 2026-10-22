//! The finite quotients Q^_{N,M} (adelic) and Q~_{N,M} (lifted), see the
//! Python module `arithkit_api.modular.quotient` for the specification.
//!
//! An element is `(e, u)`: the type `e | N` is stored as a bit mask over the
//! primes of `N` (the type group T_N is (Z/2)^omega(N), so the type product is
//! XOR), and `u = (a, b, c, d)` are residues modulo `M` standing for
//! `[[a, b], [N c, d]]` in R_0(N)/M R_0(N). The pair stands for `u W_e`.
//!
//! The maps phi_e (conjugation by W_e) are Z-linear on R_0(N), so they are
//! precomputed once as 4x4 integer matrices in the coordinates above (exact
//! division by e happens over Z, before reducing modulo M). The cocycle
//! kappa(e, e') is precomputed as a table when omega(N) is small.

use arithkit_bigint::BigInt;

use crate::infra::errors::{Error, Result};
use crate::infra::interrupt::Poll;
use crate::infra::intmat::{self, Mat2};
use crate::infra::zmod::{Modulus, gcd};
use crate::infra::{arith, interrupt};

/// The residues `(a, b, c, d)` modulo `M`.
pub type Coords = [u64; 4];

/// An element `(e, u)`; `mask` encodes `e` (see [`Quotient::type_of`]).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Elem {
    /// Bit `i` set iff the `i`-th prime of `N` divides `e`.
    pub mask: u32,
    /// The coordinates `(a, b, c, d)` in `[0, M)`.
    pub u: Coords,
}

/// A 4x4 matrix of residues acting on coordinates.
type Linear = [[u64; 4]; 4];

/// Precompute the kappa table when 4^omega(N) is at most this.
const KAPPA_TABLE_LIMIT: usize = 1 << 16;

/// The adelic or lifted quotient for given `N`, `M`.
#[derive(Debug)]
pub struct Quotient {
    n: u64,
    m: u64,
    lifted: bool,
    md: Modulus,
    n_mod: u64,
    primes: Vec<u64>,
    e_of_mask: Vec<u64>,
    masks_by_e: Vec<u32>,
    al: Vec<Mat2>,
    phi: Vec<Linear>,
    phi_inv: Vec<Linear>,
    kappa: Option<Vec<Coords>>,
}

/// The fixed Atkin--Lehner matrix W_e for the Hall divisor `e` of `n` (proof of lem:global-al):
/// `W_1 = 1`, else `[[e, y], [n, e w]]` with `w >= 1` least such that `e w = 1 mod n/e` and
/// `y = (e w - 1)/(n/e)`.
pub fn al_matrix(n: u64, e: u64) -> Mat2 {
    if e == 1 {
        return intmat::from_i64([[1, 0], [0, 1]]);
    }
    let f = n / e;
    let w = if f == 1 {
        1
    } else {
        let md = Modulus::new(f);
        md.inv(md.reduce_u64(e)).expect("e is a unit modulo n/e")
    };
    let ew = &BigInt::from(e) * &BigInt::from(w);
    let y = (&ew - &BigInt::from(1u64))
        .div_exact(&BigInt::from(f))
        .expect("exact by choice of w");
    [[BigInt::from(e), y], [BigInt::from(n), ew]]
}

impl Quotient {
    /// The quotient for `N`, `M`; `lifted` selects Q~ instead of Q^.
    pub fn new(n: u64, m: u64, lifted: bool) -> Result<Quotient> {
        let bound = 1u64 << 63;
        if !(1..bound).contains(&n) || !(1..bound).contains(&m) {
            return Err(Error::InvalidParameter("need 1 <= N, M < 2^63".into()));
        }
        let factors = arith::factor(n);
        if factors.iter().any(|&(_, k)| k > 1) {
            return Err(Error::InvalidParameter("N must be squarefree".into()));
        }
        let primes: Vec<u64> = factors.iter().map(|&(p, _)| p).collect();
        let size = 1usize << primes.len();
        let e_of_mask: Vec<u64> = (0..size)
            .map(|mask| {
                (0..primes.len())
                    .filter(|i| mask >> i & 1 == 1)
                    .map(|i| primes[i])
                    .product()
            })
            .collect();
        let mut masks_by_e: Vec<u32> = (0..size as u32).collect();
        masks_by_e.sort_by_key(|&mask| e_of_mask[mask as usize]);
        let md = Modulus::new(m);
        let mut q = Quotient {
            n,
            m,
            lifted,
            md,
            n_mod: md.reduce_u64(n),
            al: e_of_mask.iter().map(|&e| al_matrix(n, e)).collect(),
            primes,
            e_of_mask,
            masks_by_e,
            phi: Vec::new(),
            phi_inv: Vec::new(),
            kappa: None,
        };
        q.phi = (0..size as u32)
            .map(|mask| q.linear_conjugation(mask, false))
            .collect();
        q.phi_inv = (0..size as u32)
            .map(|mask| q.linear_conjugation(mask, true))
            .collect();
        if size * size <= KAPPA_TABLE_LIMIT {
            let table = (0..size * size)
                .map(|i| q.compute_kappa((i / size) as u32, (i % size) as u32))
                .collect();
            q.kappa = Some(table);
        }
        Ok(q)
    }

    /// `N`.
    pub fn n(&self) -> u64 {
        self.n
    }

    /// `M`.
    pub fn m(&self) -> u64 {
        self.m
    }

    /// Whether this is the lifted quotient Q~.
    pub fn lifted(&self) -> bool {
        self.lifted
    }

    /// Same kind, `N` and `M`.
    pub fn same_group(&self, other: &Quotient) -> bool {
        (self.lifted, self.n, self.m) == (other.lifted, other.n, other.m)
    }

    /// The positive divisors of `N` in increasing order.
    pub fn type_group(&self) -> Vec<u64> {
        self.masks_by_e
            .iter()
            .map(|&mask| self.e_of_mask[mask as usize])
            .collect()
    }

    /// The type `e` of the mask.
    pub fn type_of(&self, mask: u32) -> u64 {
        self.e_of_mask[mask as usize]
    }

    /// The mask of `e`, if `e` is a positive divisor of `N`.
    pub fn mask_of(&self, e: u64) -> Option<u32> {
        if e == 0 || !self.n.is_multiple_of(e) {
            return None;
        }
        Some(
            (0..self.primes.len())
                .filter(|&i| e.is_multiple_of(self.primes[i]))
                .map(|i| 1u32 << i)
                .sum(),
        )
    }

    /// The key of the canonical order: lexicographic on `(e, a, b, c, d)`.
    pub fn sort_key(&self, x: &Elem) -> (u64, Coords) {
        (self.type_of(x.mask), x.u)
    }

    // ----- coordinates and the ring R_0(N)/M R_0(N) --------------------------------

    /// The coordinates modulo `M` of an integer matrix in R_0(N); `None` if it is not in R_0(N).
    fn coords_of(&self, x: &Mat2) -> Option<Coords> {
        let c = x[1][0].div_exact(&BigInt::from(self.n))?;
        Some([
            x[0][0].rem_euclid_u64(self.m),
            x[0][1].rem_euclid_u64(self.m),
            c.rem_euclid_u64(self.m),
            x[1][1].rem_euclid_u64(self.m),
        ])
    }

    /// The product in R_0(N)/M R_0(N) (prop:eichler-model).
    fn twisted_mul(&self, x: &Coords, y: &Coords) -> Coords {
        let md = &self.md;
        let [a, b, c, d] = *x;
        let [a2, b2, c2, d2] = *y;
        let nb = md.mul(self.n_mod, b);
        let nc = md.mul(self.n_mod, c);
        [
            md.add(md.mul(a, a2), md.mul(nb, c2)),
            md.add(md.mul(a, b2), md.mul(b, d2)),
            md.add(md.mul(c, a2), md.mul(d, c2)),
            md.add(md.mul(nc, b2), md.mul(d, d2)),
        ]
    }

    /// `det u = a d - N b c` modulo `M`.
    pub fn det(&self, u: &Coords) -> u64 {
        let md = &self.md;
        let [a, b, c, d] = *u;
        md.sub(md.mul(a, d), md.mul(md.mul(self.n_mod, b), c))
    }

    /// Whether `u` satisfies the determinant condition of this group.
    pub fn valid_det(&self, u: &Coords) -> bool {
        let det = self.det(u);
        if self.lifted {
            det == self.md.one()
        } else {
            self.md.is_unit(det)
        }
    }

    /// Whether `det u = 1` modulo `M`.
    pub fn det_is_one(&self, u: &Coords) -> bool {
        self.det(u) == self.md.one()
    }

    /// The inverse of the unit `u`: `det^{-1} (d, -b, -c, a)`.
    fn unit_inverse(&self, u: &Coords) -> Coords {
        let md = &self.md;
        let t = md.inv(self.det(u)).expect("u is a unit");
        let [a, b, c, d] = *u;
        [
            md.mul(t, d),
            md.neg(md.mul(t, b)),
            md.neg(md.mul(t, c)),
            md.mul(t, a),
        ]
    }

    /// The coordinate matrix of x -> W_e x W_e^{-1} (or of its inverse x -> W_e^{-1} x W_e),
    /// computed over Z on the basis E11, E12, N E21, E22 of R_0(N).
    fn linear_conjugation(&self, mask: u32, inverse: bool) -> Linear {
        let w = &self.al[mask as usize];
        let e = BigInt::from(self.type_of(mask));
        let zero = || BigInt::zero();
        let one = || BigInt::from(1u64);
        let basis: [Mat2; 4] = [
            [[one(), zero()], [zero(), zero()]],
            [[zero(), one()], [zero(), zero()]],
            [[zero(), zero()], [BigInt::from(self.n), zero()]],
            [[zero(), zero()], [zero(), one()]],
        ];
        let mut result: Linear = [[0; 4]; 4];
        for (j, x) in basis.iter().enumerate() {
            let y = if inverse {
                intmat::mul(&intmat::mul(&intmat::adj(w), x), w)
            } else {
                intmat::mul(&intmat::mul(w, x), &intmat::adj(w))
            };
            let y =
                intmat::div_exact(&y, &e).expect("W_e normalises R_0(N): division by e is exact");
            let column = self.coords_of(&y).expect("W_e normalises R_0(N)");
            for i in 0..4 {
                result[i][j] = column[i];
            }
        }
        result
    }

    fn apply(&self, l: &Linear, u: &Coords) -> Coords {
        let md = &self.md;
        let mut out = [0u64; 4];
        for i in 0..4 {
            let mut s = 0u64;
            for j in 0..4 {
                s = md.add(s, md.mul(l[i][j], u[j]));
            }
            out[i] = s;
        }
        out
    }

    /// kappa(e, f) = gcd(e, f)^{-1} W_e W_f W_{e*f}^{-1} in Gamma_0(N) (prop:al-encoding (2)).
    fn compute_kappa(&self, m1: u32, m2: u32) -> Coords {
        let (e, f) = (self.type_of(m1), self.type_of(m2));
        let ef = self.type_of(m1 ^ m2);
        let k = intmat::mul(
            &intmat::mul(&self.al[m1 as usize], &self.al[m2 as usize]),
            &intmat::adj(&self.al[(m1 ^ m2) as usize]),
        );
        let k = intmat::div_exact(&k, &BigInt::from(gcd(e, f) * ef)).expect("kappa is integral");
        assert!(
            intmat::det(&k) == BigInt::from(1u64),
            "kappa has determinant 1"
        );
        self.coords_of(&k).expect("kappa lies in Gamma_0(N)")
    }

    fn kappa(&self, m1: u32, m2: u32) -> Coords {
        match &self.kappa {
            Some(table) => table[((m1 as usize) << self.primes.len()) | m2 as usize],
            None => self.compute_kappa(m1, m2),
        }
    }

    // ----- the group law -----------------------------------------------------------

    /// The element `(e, u)` with `u` already reduced modulo `M`.
    pub fn element(&self, e: u64, u: Coords) -> Result<Elem> {
        let mask = self.mask_of(e).ok_or_else(|| {
            Error::NotInGroup(format!("{e} is not a positive divisor of N = {}", self.n))
        })?;
        if !self.valid_det(&u) {
            return Err(Error::NotInGroup(if self.lifted {
                "det u is not 1".into()
            } else {
                "det u is not a unit".into()
            }));
        }
        Ok(Elem { mask, u })
    }

    /// Reduces arbitrary integers modulo `M`.
    pub fn reduce(&self, x: &BigInt) -> u64 {
        x.rem_euclid_u64(self.m)
    }

    /// The identity `(1, (1, 0, 0, 1))`.
    pub fn identity(&self) -> Elem {
        let one = self.md.one();
        Elem {
            mask: 0,
            u: [one, 0, 0, one],
        }
    }

    /// The image of `W_e`, i.e. `(e, (1, 0, 0, 1))`.
    pub fn al_element(&self, e: u64) -> Result<Elem> {
        let identity = self.identity();
        self.element(e, identity.u)
    }

    /// `(e, u)(f, v) = (e * f, u phi_e(v) kappa(e, f))` (prop:al-encoding (3)).
    pub fn mul(&self, x: &Elem, y: &Elem) -> Elem {
        let t = self.apply(&self.phi[x.mask as usize], &y.u);
        let u = self.twisted_mul(&x.u, &t);
        let u = self.twisted_mul(&u, &self.kappa(x.mask, y.mask));
        Elem {
            mask: x.mask ^ y.mask,
            u,
        }
    }

    /// The inverse `(e, v)` of `(e, u)`: `v = phi_e^{-1}(u^{-1} kappa(e, e)^{-1})`.
    pub fn inverse(&self, x: &Elem) -> Elem {
        let k = self.unit_inverse(&self.kappa(x.mask, x.mask));
        let target = self.twisted_mul(&self.unit_inverse(&x.u), &k);
        Elem {
            mask: x.mask,
            u: self.apply(&self.phi_inv[x.mask as usize], &target),
        }
    }

    /// The order of the element.
    pub fn element_order(&self, x: &Elem) -> Result<u64> {
        let identity = self.identity();
        let mut poll = Poll::new(1 << 12);
        let (mut power, mut k) = (*x, 1u64);
        while power != identity {
            poll.tick()?;
            power = self.mul(&power, x);
            k += 1;
        }
        Ok(k)
    }

    fn pow_u64(&self, x: &Elem, mut k: u64) -> Elem {
        let (mut base, mut result) = (*x, self.identity());
        while k > 0 {
            if k & 1 == 1 {
                result = self.mul(&result, &base);
            }
            base = self.mul(&base, &base);
            k >>= 1;
        }
        result
    }

    /// The `k`-th power; negative `k` gives powers of the inverse.
    pub fn pow(&self, x: &Elem, k: &BigInt) -> Result<Elem> {
        if let Some(small) = k.to_i64() {
            let base = if small < 0 { self.inverse(x) } else { *x };
            return Ok(self.pow_u64(&base, small.unsigned_abs()));
        }
        let order = self.element_order(x)?;
        Ok(self.pow_u64(x, k.rem_euclid_u64(order)))
    }

    /// The image of the integral matrix `g` with positive determinant representing an element
    /// of Gamma_0~(N)^* modulo Q_{>0} (lifted quotient). Write `g = q gamma W_e`; then
    /// `g adj(W_e) = q e gamma`, and `s = q e = sqrt(det(g) e)`.
    pub fn from_matrix(&self, g: &Mat2) -> Result<Elem> {
        let not_in_group = || Error::NotInGroup("not in Gamma_0(N)^* modulo Q_{>0}".into());
        let d = intmat::det(g);
        if d.signum() <= 0 {
            return Err(Error::NotInGroup("the determinant must be positive".into()));
        }
        let mut e = 1u64;
        for &p in &self.primes {
            let p_big = BigInt::from(p);
            let (mut rest, mut v) = (d.clone(), 0u32);
            while let Some(r) = rest.div_exact(&p_big) {
                rest = r;
                v += 1;
            }
            if v % 2 == 1 {
                e *= p;
            }
        }
        let mask = self.mask_of(e).expect("e divides N");
        let s = (&d * &BigInt::from(e))
            .sqrt_exact()
            .ok_or_else(not_in_group)?;
        let gamma = intmat::div_exact(&intmat::mul(g, &intmat::adj(&self.al[mask as usize])), &s)
            .ok_or_else(not_in_group)?;
        let u = self.coords_of(&gamma).ok_or_else(not_in_group)?;
        Ok(Elem { mask, u })
    }

    /// |(R_0(N)/M R_0(N))^x|, a product over the prime powers p^k exactly dividing M of
    /// p^(4k-2) (p-1)^2 if p | N and |GL_2(Z/p^k)| = p^(4k-4) (p^2-1)(p^2-p) otherwise.
    fn unit_group_order(&self) -> BigInt {
        let mut total = BigInt::from(1u64);
        for (p, k) in arith::factor(self.m) {
            let pb = BigInt::from(p);
            let power = |exp: u32| (0..exp).fold(BigInt::from(1u64), |acc, _| &acc * &pb);
            let p_minus_1 = BigInt::from(p - 1);
            let factor = if self.n.is_multiple_of(p) {
                &power(4 * k - 2) * &(&p_minus_1 * &p_minus_1)
            } else {
                // (p^2 - 1)(p^2 - p) = (p - 1)^2 p (p + 1)
                let p_plus_1 = &pb + &BigInt::from(1u64);
                &(&power(4 * k - 3) * &(&p_minus_1 * &p_minus_1)) * &p_plus_1
            };
            total = &total * &factor;
        }
        total
    }

    /// The order of the group.
    pub fn order(&self) -> BigInt {
        let size = &BigInt::from(self.e_of_mask.len() as u64) * &self.unit_group_order();
        if self.lifted {
            size.div_exact(&BigInt::from(arith::euler_phi(self.m)))
                .expect("phi(M) divides the order")
        } else {
            size
        }
    }

    /// All elements in canonical order.
    pub fn elements(&self) -> Result<Vec<Elem>> {
        let mut out = Vec::new();
        let mut poll = Poll::new(1 << 12);
        for &mask in &self.masks_by_e {
            for a in 0..self.m {
                for b in 0..self.m {
                    for c in 0..self.m {
                        poll.tick()?;
                        for d in 0..self.m {
                            let u = [a, b, c, d];
                            if self.valid_det(&u) {
                                out.push(Elem { mask, u });
                            }
                        }
                    }
                }
            }
        }
        interrupt::check()?;
        Ok(out)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn all_quotients() -> Vec<Quotient> {
        let mut out = Vec::new();
        for (n, m) in [
            (1, 1),
            (1, 2),
            (2, 2),
            (6, 2),
            (2, 3),
            (3, 4),
            (6, 4),
            (5, 5),
            (10, 3),
        ] {
            for lifted in [false, true] {
                out.push(Quotient::new(n, m, lifted).unwrap());
            }
        }
        out
    }

    #[test]
    fn group_axioms_and_order() {
        for q in all_quotients() {
            let els = q.elements().unwrap();
            assert_eq!(
                BigInt::from(els.len() as u64),
                q.order(),
                "N={} M={}",
                q.n,
                q.m
            );
            let one = q.identity();
            let sample: Vec<&Elem> = els.iter().step_by(els.len().div_ceil(10)).collect();
            for x in &sample {
                assert_eq!(q.mul(x, &one), **x);
                assert_eq!(q.mul(&q.inverse(x), x), one);
                for y in &sample {
                    for z in sample.iter().take(3) {
                        assert_eq!(q.mul(&q.mul(x, y), z), q.mul(x, &q.mul(y, z)));
                    }
                }
            }
        }
    }

    #[test]
    fn invalid_parameters() {
        assert!(Quotient::new(4, 3, false).is_err());
        assert!(Quotient::new(0, 3, false).is_err());
        assert!(Quotient::new(6, 0, true).is_err());
        assert!(Quotient::new(6, 1 << 63, true).is_err());
    }

    #[test]
    fn al_matrices_have_determinant_e() {
        for n in [1u64, 2, 6, 30, 210, 2310] {
            for e in 1..=n {
                if n % e == 0 && gcd(e, n / e) == 1 {
                    assert_eq!(intmat::det(&al_matrix(n, e)), BigInt::from(e));
                }
            }
        }
    }
}
