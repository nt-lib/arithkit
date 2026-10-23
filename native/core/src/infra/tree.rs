//! The Bruhat--Tits tree of PGL_2(Q_p) in vertex coordinates (maths: def:vertex-coordinates).
//!
//! A vertex `(m, r, s)` is the class of the column span of `[[p^m, b], [0, 1]]` with
//! `b = r / p^s`, `0 <= b < p^m`, and `s = 0` or `p` not dividing `r`. Integers only.

use std::collections::{HashMap, HashSet, VecDeque};

use arithkit_bigint::BigInt;

use crate::infra::intmat::{self, Mat2};

/// A vertex `(m, r, s)`.
#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Vertex {
    /// The exponent `m`.
    pub m: i64,
    /// The numerator `r` of `b = r / p^s`.
    pub r: BigInt,
    /// The exponent `s` of the denominator.
    pub s: u32,
}

/// The base vertex `(0, 0, 0)`.
pub fn origin() -> Vertex {
    Vertex {
        m: 0,
        r: BigInt::zero(),
        s: 0,
    }
}

/// `o(p)_p = (-1, 0, 0)`, the other end of the standard edge.
pub fn standard_neighbour() -> Vertex {
    Vertex {
        m: -1,
        r: BigInt::zero(),
        s: 0,
    }
}

fn pow(p: &BigInt, e: i64) -> BigInt {
    p.pow(u32::try_from(e).expect("nonnegative exponent"))
}

/// The vertex `(m, b)` for `b = numerator / p^s`, with `b` reduced modulo `p^m` into `[0, p^m)`.
pub fn normalise(p: &BigInt, m: i64, numerator: &BigInt, s: u32) -> Vertex {
    let mut t = i64::from(s).max(-m).max(0);
    let mut big = (numerator * &pow(p, t - i64::from(s))).rem_euclid(&pow(p, m + t));
    while t > 0 {
        match big.div_exact(p) {
            Some(q) => {
                big = q;
                t -= 1;
            }
            None => break,
        }
    }
    if big.is_zero() {
        t = 0;
    }
    Vertex {
        m,
        r: big,
        s: u32::try_from(t).expect("small exponent"),
    }
}

/// The `p + 1` neighbours (maths: lem:neighbours); `p` must be small enough to enumerate.
pub fn neighbours(p: u64, v: &Vertex) -> Vec<Vertex> {
    let pb = BigInt::from(p);
    let t = i64::from(v.s).max(-v.m).max(0);
    let big = &v.r * &pow(&pb, t - i64::from(v.s));
    let step = pow(&pb, v.m + t);
    let mut out: Vec<Vertex> = (0..p)
        .map(|j| {
            normalise(
                &pb,
                v.m + 1,
                &(&big + &(&step * &BigInt::from(j))),
                u32::try_from(t).expect("small"),
            )
        })
        .collect();
    out.push(normalise(&pb, v.m - 1, &v.r, v.s));
    out
}

/// An integral matrix `X = p^t [[p^m, b], [0, 1]]` spanning a lattice of the class `v`.
pub fn basis(p: &BigInt, v: &Vertex) -> Mat2 {
    let t = i64::from(v.s).max(-v.m).max(0);
    [
        [pow(p, v.m + t), &v.r * &pow(p, t - i64::from(v.s))],
        [BigInt::zero(), pow(p, t)],
    ]
}

/// Whether the integral matrix `g` (nonzero determinant) fixes `v` (lem:fixed-vertex-test).
pub fn fixes(p: u64, g: &Mat2, v: &Vertex) -> bool {
    let pb = BigInt::from(p);
    let k = intmat::det(g).valuation(&pb).expect("nonzero determinant");
    if k % 2 == 1 {
        return false;
    }
    let x = basis(&pb, v);
    let y = intmat::mul(&intmat::mul(&intmat::adj(&x), g), &x);
    let bound = intmat::det(&x).valuation(&pb).expect("nonzero") + k / 2;
    y.iter()
        .flatten()
        .all(|entry| entry.valuation(&pb).is_none_or(|e| e >= bound))
}

/// The vertices at distance `<= radius` from one of the sources, in breadth first order.
pub fn ball(p: u64, sources: &[Vertex], radius: u32) -> Vec<Vertex> {
    let mut seen: HashSet<Vertex> = sources.iter().cloned().collect();
    let mut order: Vec<Vertex> = sources.to_vec();
    let mut queue: VecDeque<(Vertex, u32)> = sources.iter().cloned().map(|v| (v, 0)).collect();
    while let Some((v, dist)) = queue.pop_front() {
        if dist == radius {
            continue;
        }
        for w in neighbours(p, &v) {
            if seen.insert(w.clone()) {
                order.push(w.clone());
                queue.push_back((w, dist + 1));
            }
        }
    }
    order
}

/// A vertex farthest from `start` inside the subtree, and the breadth first parents.
fn farthest(
    p: u64,
    vertices: &HashSet<Vertex>,
    start: &Vertex,
) -> (Vertex, HashMap<Vertex, Option<Vertex>>) {
    let mut parent: HashMap<Vertex, Option<Vertex>> = HashMap::from([(start.clone(), None)]);
    let mut queue = VecDeque::from([start.clone()]);
    let mut last = start.clone();
    while let Some(v) = queue.pop_front() {
        last = v.clone();
        for w in neighbours(p, &v) {
            if vertices.contains(&w) && !parent.contains_key(&w) {
                parent.insert(w.clone(), Some(v.clone()));
                queue.push_back(w);
            }
        }
    }
    (last, parent)
}

/// The centre of the finite nonempty subtree spanned by `vertices` (lem:centre): `(v, v)` for a
/// vertex, the two endpoints in increasing order for an edge midpoint.
pub fn centre(p: u64, vertices: &HashSet<Vertex>) -> (Vertex, Vertex) {
    let start = vertices.iter().min().expect("nonempty").clone();
    let (a, _) = farthest(p, vertices, &start);
    let (b, parent) = farthest(p, vertices, &a);
    let mut path = vec![b];
    while let Some(Some(prev)) = parent.get(path.last().expect("nonempty")) {
        path.push(prev.clone());
    }
    let length = path.len() - 1;
    if length % 2 == 0 {
        let mid = path[length / 2].clone();
        (mid.clone(), mid)
    } else {
        let (x, y) = (path[length / 2].clone(), path[length / 2 + 1].clone());
        if x < y { (x, y) } else { (y, x) }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn neighbours_are_symmetric() {
        for p in [2u64, 3, 5] {
            for v in ball(p, &[origin()], 3) {
                for w in neighbours(p, &v) {
                    assert!(neighbours(p, &w).contains(&v), "{v:?} {w:?}");
                }
            }
            assert_eq!(ball(p, &[origin()], 1).len() as u64, p + 2);
        }
    }

    #[test]
    fn gamma0_fixes_the_snake() {
        // [[1, 0], [9, 1]] lies in Gamma_0(9): it fixes o, o(3), o(9).
        let g = intmat::from_i64([[1, 0], [9, 1]]);
        let o3 = standard_neighbour();
        let o9 = Vertex {
            m: -2,
            r: BigInt::zero(),
            s: 0,
        };
        assert!(fixes(3, &g, &origin()) && fixes(3, &g, &o3) && fixes(3, &g, &o9));
        let other = Vertex {
            m: 1,
            r: BigInt::from(1u64),
            s: 0,
        };
        // [[1, 0], [1, 1]] maps the line of (1, 1) to that of (1, 2) modulo 3.
        assert!(!fixes(3, &intmat::from_i64([[1, 0], [1, 1]]), &other));
        assert!(fixes(3, &intmat::from_i64([[1, 0], [3, 1]]), &other));
        let fixed: HashSet<Vertex> = [origin(), o3.clone(), o9].into_iter().collect();
        assert_eq!(centre(3, &fixed), (o3.clone(), o3));
    }
}
