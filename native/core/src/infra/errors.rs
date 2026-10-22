//! Errors of user-reachable failures. Each variant maps to one exception class
//! of `arithkit_api.errors` (or `KeyboardInterrupt`). A panic is always a bug.

use std::fmt;

/// An error caused by the input, or an interrupt.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Error {
    /// `arithkit_api.errors.InvalidParameterError`.
    InvalidParameter(String),
    /// `arithkit_api.errors.NotInGroupError`.
    NotInGroup(String),
    /// `arithkit_api.errors.ParentMismatchError`.
    ParentMismatch(String),
    /// The computation was interrupted (Ctrl-C), `KeyboardInterrupt`.
    Interrupted,
}

/// Results of fallible operations.
pub type Result<T> = std::result::Result<T, Error>;

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::InvalidParameter(msg) | Error::NotInGroup(msg) | Error::ParentMismatch(msg) => {
                write!(f, "{msg}")
            }
            Error::Interrupted => write!(f, "interrupted"),
        }
    }
}

impl std::error::Error for Error {}
