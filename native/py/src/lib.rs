//! PyO3 bindings: the extension module `arithkit._native`.
//!
//! The module tree `modular/...` mirrors `arithkit-core`. Binding structs carry
//! the prefix `Py` (`PyQuotientElement` is exposed as `QuotientElement`).
//! Errors are mapped to the classes of `arithkit_api.errors`; JSON goes through
//! `arithkit_api._json`, so that malformed input is rejected exactly as in the
//! toy implementation.

use pyo3::prelude::*;

mod convert;
mod modular;

/// Asks Python whether a signal (Ctrl-C) is pending; true means stop.
fn interrupt_hook() -> bool {
    Python::attach(|py| py.check_signals().is_err())
}

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    arithkit_core::infra::interrupt::set_hook(interrupt_hook);
    m.add_class::<modular::quotient::PyQuotientGroup>()?;
    m.add_class::<modular::quotient::PyGL2ASubQuotient>()?;
    m.add_class::<modular::quotient::PyGL2QSubQuotient>()?;
    m.add_class::<modular::quotient::PyQuotientElement>()?;
    m.add_class::<modular::subgroup::PyQuotientSubgroup>()?;
    m.add_function(wrap_pyfunction!(modular::quotient::quotient_from_json, m)?)?;
    m.add_function(wrap_pyfunction!(modular::subgroup::subgroup_from_json, m)?)?;
    Ok(())
}
