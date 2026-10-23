//! Conversions between Python objects and core types, error mapping and JSON.

use arithkit_bigint::BigInt;
use arithkit_core::infra::errors::Error;
use arithkit_core::infra::intmat::Mat2;
use pyo3::exceptions::{PyKeyboardInterrupt, PyOverflowError, PyTypeError};
use pyo3::prelude::*;
use pyo3::types::{PyTuple, PyType};

/// The exception class `arithkit_api.errors.<name>`.
fn error_class<'py>(py: Python<'py>, name: &str) -> PyResult<Bound<'py, PyType>> {
    Ok(py
        .import("arithkit_api.errors")?
        .getattr(name)?
        .cast_into::<PyType>()?)
}

/// Raises an exception of class `arithkit_api.errors.<name>`.
pub fn api_error(py: Python<'_>, name: &str, msg: impl Into<String>) -> PyErr {
    match error_class(py, name) {
        Ok(cls) => PyErr::from_type(cls, msg.into()),
        Err(err) => err,
    }
}

/// Maps a core error to the corresponding Python exception.
pub fn to_pyerr(py: Python<'_>, err: Error) -> PyErr {
    match err {
        Error::InvalidParameter(msg) => api_error(py, "InvalidParameterError", msg),
        Error::NotInGroup(msg) => api_error(py, "NotInGroupError", msg),
        Error::ParentMismatch(msg) => api_error(py, "ParentMismatchError", msg),
        Error::Interrupted => PyKeyboardInterrupt::new_err(()),
    }
}

/// A Python integer (anything with `__index__`) as a [`BigInt`]; TypeError otherwise.
pub fn to_bigint(obj: &Bound<'_, PyAny>) -> PyResult<BigInt> {
    match obj.extract::<i64>() {
        Ok(x) => Ok(BigInt::from(x)),
        Err(err) if err.is_instance_of::<PyOverflowError>(obj.py()) => {
            let py = obj.py();
            let index = py.import("operator")?.call_method1("index", (obj,))?;
            let hex: String = py
                .import("builtins")?
                .call_method1("format", (index, "x"))?
                .extract()?;
            Ok(BigInt::from_hex(&hex).expect("Python produced a valid hexadecimal integer"))
        }
        Err(err) => Err(err),
    }
}

/// A [`BigInt`] as a Python integer.
pub fn bigint_to_py<'py>(py: Python<'py>, x: &BigInt) -> PyResult<Bound<'py, PyAny>> {
    py.import("builtins")?.call_method1("int", (x.to_hex(), 16))
}

/// A Python integer as a `u64` if it lies in `[0, 2^64)`, `None` if it is out of range.
pub fn to_u64_or_none(obj: &Bound<'_, PyAny>) -> PyResult<Option<u64>> {
    Ok(to_bigint(obj)?.to_u64())
}

/// `u` as a tuple of four Python integers.
pub fn tuple_of_four(u: &Bound<'_, PyAny>) -> PyResult<[BigInt; 4]> {
    let t = u
        .cast::<PyTuple>()
        .map_err(|_| PyTypeError::new_err("u must be a tuple of four integers"))?;
    if t.len() != 4 {
        return Err(PyTypeError::new_err("u must be a tuple of four integers"));
    }
    Ok([
        to_bigint(&t.get_item(0)?)?,
        to_bigint(&t.get_item(1)?)?,
        to_bigint(&t.get_item(2)?)?,
        to_bigint(&t.get_item(3)?)?,
    ])
}

/// `g` as a tuple of two tuples of two Python integers.
pub fn matrix(g: &Bound<'_, PyAny>) -> PyResult<Mat2> {
    let msg = "g must be a tuple of two tuples of two integers";
    let t = g.cast::<PyTuple>().map_err(|_| PyTypeError::new_err(msg))?;
    if t.len() != 2 {
        return Err(PyTypeError::new_err(msg));
    }
    let row = |i: usize| -> PyResult<[BigInt; 2]> {
        let item = t.get_item(i)?;
        let r = item
            .cast::<PyTuple>()
            .map_err(|_| PyTypeError::new_err(msg))?;
        if r.len() != 2 {
            return Err(PyTypeError::new_err(msg));
        }
        Ok([to_bigint(&r.get_item(0)?)?, to_bigint(&r.get_item(1)?)?])
    };
    Ok([row(0)?, row(1)?])
}

/// The module `arithkit_api._json`.
pub fn json_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    py.import("arithkit_api._json")
}

/// `arithkit_api._json.dumps(value)`.
pub fn dumps(value: &Bound<'_, PyAny>) -> PyResult<String> {
    json_module(value.py())?
        .call_method1("dumps", (value,))?
        .extract()
}

/// `arithkit_api._json.loads(text)`.
pub fn loads<'py>(text: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
    json_module(text.py())?.call_method1("loads", (text,))
}
