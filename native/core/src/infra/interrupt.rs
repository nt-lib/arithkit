//! Cooperative interruption of long computations.
//!
//! Long loops call [`check`] regularly. With the Cargo feature `interrupt`
//! (default) it asks a hook installed by the embedding layer (the PyO3
//! bindings ask Python whether Ctrl-C was pressed); without the feature it
//! compiles to nothing. There are no signal handlers here.
//!
//! Limitation: a single long bigint operation cannot be interrupted.

use crate::infra::errors::{Error, Result};

#[cfg(feature = "interrupt")]
static HOOK: std::sync::OnceLock<fn() -> bool> = std::sync::OnceLock::new();

/// Installs the hook; it returns true when the computation should stop.
/// Later calls are ignored.
#[cfg(feature = "interrupt")]
pub fn set_hook(hook: fn() -> bool) {
    let _ = HOOK.set(hook);
}

/// Without the `interrupt` feature there is nothing to install.
#[cfg(not(feature = "interrupt"))]
pub fn set_hook(_hook: fn() -> bool) {}

/// `Err(Error::Interrupted)` if the hook asks to stop.
#[cfg(feature = "interrupt")]
pub fn check() -> Result<()> {
    match HOOK.get() {
        Some(hook) if hook() => Err(Error::Interrupted),
        _ => Ok(()),
    }
}

/// Without the `interrupt` feature this is a no-op.
#[cfg(not(feature = "interrupt"))]
#[inline(always)]
pub fn check() -> Result<()> {
    let _ = Error::Interrupted;
    Ok(())
}

/// Calls [`check`] every `period` steps; `step` counts the steps.
pub struct Poll {
    count: u32,
    period: u32,
}

impl Poll {
    /// Checks once every `period` calls of [`Poll::tick`].
    pub fn new(period: u32) -> Poll {
        Poll {
            count: 0,
            period: period.max(1),
        }
    }

    /// Counts one step and checks for an interrupt every `period` steps.
    pub fn tick(&mut self) -> Result<()> {
        self.count += 1;
        if self.count >= self.period {
            self.count = 0;
            check()
        } else {
            Ok(())
        }
    }
}
