//! Integer 2x2 matrices `[[a, b], [c, d]]` over [`BigInt`].

use arithkit_bigint::BigInt;

/// An integer 2x2 matrix, rows first.
pub type Mat2 = [[BigInt; 2]; 2];

/// The matrix with the given small entries.
pub fn from_i64(m: [[i64; 2]; 2]) -> Mat2 {
    m.map(|row| row.map(BigInt::from))
}

/// The product `x y`.
pub fn mul(x: &Mat2, y: &Mat2) -> Mat2 {
    let entry = |i: usize, j: usize| &(&x[i][0] * &y[0][j]) + &(&x[i][1] * &y[1][j]);
    [[entry(0, 0), entry(0, 1)], [entry(1, 0), entry(1, 1)]]
}

/// The adjugate: `x adj(x) = det(x) 1`.
pub fn adj(x: &Mat2) -> Mat2 {
    [[x[1][1].clone(), -&x[0][1]], [-&x[1][0], x[0][0].clone()]]
}

/// The determinant.
pub fn det(x: &Mat2) -> BigInt {
    &(&x[0][0] * &x[1][1]) - &(&x[0][1] * &x[1][0])
}

/// `x / q` if `q` divides every entry.
pub fn div_exact(x: &Mat2, q: &BigInt) -> Option<Mat2> {
    Some([
        [x[0][0].div_exact(q)?, x[0][1].div_exact(q)?],
        [x[1][0].div_exact(q)?, x[1][1].div_exact(q)?],
    ])
}
