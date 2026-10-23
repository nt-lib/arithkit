//! Bindings of `arithkit_core::modular::quotient`; see `arithkit_api.modular.quotient`.

use std::sync::Arc;

use arithkit_core::modular::quotient::{Elem, Quotient};
use arithkit_core::modular::subgroup::Subgroup;
use pyo3::basic::CompareOp;
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};

use crate::convert::{
    api_error, dumps, json_module, loads, matrix, to_bigint, to_pyerr, to_u64_or_none,
    tuple_of_four,
};
use crate::modular::subgroup::PyQuotientSubgroup;

/// Shared base class of `GL2ASubQuotient` and `GL2QSubQuotient`.
#[pyclass(name = "_QuotientGroup", module = "arithkit._native", subclass, frozen)]
pub struct PyQuotientGroup {
    pub q: Arc<Quotient>,
}

/// The adelic quotient Q^_{N,M}; see `arithkit_api.modular.quotient.GL2ASubQuotient`.
#[pyclass(name = "GL2ASubQuotient", module = "arithkit._native", extends = PyQuotientGroup, frozen)]
pub struct PyGL2ASubQuotient;

/// The lifted quotient Q~_{N,M}; see `arithkit_api.modular.quotient.GL2QSubQuotient`.
#[pyclass(name = "GL2QSubQuotient", module = "arithkit._native", extends = PyQuotientGroup, frozen)]
pub struct PyGL2QSubQuotient;

/// An element (e, u); see `arithkit_api.modular.quotient.QuotientElement`.
#[pyclass(name = "QuotientElement", module = "arithkit._native", frozen)]
pub struct PyQuotientElement {
    pub parent: Py<PyAny>,
    pub q: Arc<Quotient>,
    pub x: Elem,
}

/// A new parent object.
pub fn new_parent(py: Python<'_>, n: u64, m: u64, lifted: bool) -> PyResult<Py<PyAny>> {
    let q = Quotient::new(n, m, lifted).map_err(|e| to_pyerr(py, e))?;
    let base = PyQuotientGroup { q: Arc::new(q) };
    if lifted {
        Ok(Py::new(
            py,
            PyClassInitializer::from(base).add_subclass(PyGL2QSubQuotient),
        )?
        .into_any())
    } else {
        Ok(Py::new(
            py,
            PyClassInitializer::from(base).add_subclass(PyGL2ASubQuotient),
        )?
        .into_any())
    }
}

/// `N` or `M` from a Python integer; out of range gives InvalidParameterError.
fn parameter(py: Python<'_>, obj: &Bound<'_, PyAny>) -> PyResult<u64> {
    match to_u64_or_none(obj)? {
        Some(x) => Ok(x),
        None => Err(api_error(
            py,
            "InvalidParameterError",
            "need 1 <= N, M < 2^63",
        )),
    }
}

/// The type e from a Python integer; values that cannot divide N give NotInGroupError.
fn type_value(py: Python<'_>, q: &Quotient, obj: &Bound<'_, PyAny>) -> PyResult<u64> {
    match to_u64_or_none(obj)? {
        Some(e) if q.mask_of(e).is_some() => Ok(e),
        _ => Err(api_error(
            py,
            "NotInGroupError",
            format!("not a positive divisor of N = {}", q.n()),
        )),
    }
}

impl PyQuotientGroup {
    fn element(slf: &Bound<'_, Self>, x: Elem) -> PyQuotientElement {
        PyQuotientElement {
            parent: slf.clone().into_any().unbind(),
            q: slf.get().q.clone(),
            x,
        }
    }

    /// `x` as an element of this group: TypeError for non-elements, ParentMismatchError
    /// for elements of another parent.
    pub fn own(&self, py: Python<'_>, x: &Bound<'_, PyAny>) -> PyResult<Elem> {
        let el = x
            .cast::<PyQuotientElement>()
            .map_err(|_| PyTypeError::new_err("expected a native QuotientElement"))?
            .get();
        if !el.q.same_group(&self.q) {
            return Err(api_error(
                py,
                "ParentMismatchError",
                "element of a different parent",
            ));
        }
        Ok(el.x)
    }

    fn json_value<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let kind = if self.q.lifted() {
            "GL2QSubQuotient"
        } else {
            "GL2ASubQuotient"
        };
        json_module(py)?.call_method1("encode_quotient", (kind, self.q.n(), self.q.m()))
    }
}

/// The JSON value `[e, [a, b, c, d]]` of an element.
pub fn element_json_value<'py>(
    py: Python<'py>,
    q: &Quotient,
    x: &Elem,
) -> PyResult<Bound<'py, PyAny>> {
    let coords = PyTuple::new(py, x.u)?;
    json_module(py)?.call_method1("encode_element", (q.type_of(x.mask), coords))
}

/// Decodes and validates the JSON value of an element of `q`.
pub fn element_from_value(
    py: Python<'_>,
    q: &Quotient,
    value: &Bound<'_, PyAny>,
) -> PyResult<Elem> {
    let (e, u): (u64, (u64, u64, u64, u64)) = json_module(py)?
        .call_method1("decode_element", (value, q.n(), q.m()))?
        .extract()?;
    q.element(e, [u.0, u.1, u.2, u.3])
        .map_err(|err| to_pyerr(py, err))
}

#[pymethods]
impl PyQuotientGroup {
    #[getter(N)]
    fn n(&self) -> u64 {
        self.q.n()
    }

    #[getter(M)]
    fn m(&self) -> u64 {
        self.q.m()
    }

    fn __call__(
        slf: &Bound<'_, Self>,
        e: &Bound<'_, PyAny>,
        u: &Bound<'_, PyAny>,
    ) -> PyResult<PyQuotientElement> {
        let py = slf.py();
        let q = &slf.get().q;
        let e = type_value(py, q, e)?;
        let u = tuple_of_four(u)?;
        let coords = [
            q.reduce(&u[0]),
            q.reduce(&u[1]),
            q.reduce(&u[2]),
            q.reduce(&u[3]),
        ];
        let x = q.element(e, coords).map_err(|err| to_pyerr(py, err))?;
        Ok(Self::element(slf, x))
    }

    fn identity(slf: &Bound<'_, Self>) -> PyQuotientElement {
        Self::element(slf, slf.get().q.identity())
    }

    fn al_element(slf: &Bound<'_, Self>, e: &Bound<'_, PyAny>) -> PyResult<PyQuotientElement> {
        let py = slf.py();
        let q = &slf.get().q;
        let e = type_value(py, q, e)?;
        let x = q.al_element(e).map_err(|err| to_pyerr(py, err))?;
        Ok(Self::element(slf, x))
    }

    fn type_group<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyTuple>> {
        PyTuple::new(py, self.q.type_group())
    }

    fn order<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let hex = self.q.order().to_hex();
        py.import("builtins")?.call_method1("int", (hex, 16))
    }

    fn elements<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyTuple>> {
        let py = slf.py();
        let els = slf.get().q.elements().map_err(|err| to_pyerr(py, err))?;
        let objs = els
            .into_iter()
            .map(|x| Bound::new(py, Self::element(slf, x)))
            .collect::<PyResult<Vec<_>>>()?;
        PyTuple::new(py, objs)
    }

    fn subgroup(slf: &Bound<'_, Self>, gens: &Bound<'_, PyAny>) -> PyResult<PyQuotientSubgroup> {
        let py = slf.py();
        let this = slf.get();
        let mut elems = Vec::new();
        for g in gens.try_iter()? {
            elems.push(this.own(py, &g?)?);
        }
        let sub = Subgroup::generated(&this.q, &elems).map_err(|err| to_pyerr(py, err))?;
        Ok(PyQuotientSubgroup {
            parent: slf.clone().into_any().unbind(),
            q: this.q.clone(),
            sub: Arc::new(sub),
        })
    }

    fn element_from_json(
        slf: &Bound<'_, Self>,
        text: &Bound<'_, PyAny>,
    ) -> PyResult<PyQuotientElement> {
        let py = slf.py();
        let x = element_from_value(py, &slf.get().q, &loads(text)?)?;
        Ok(Self::element(slf, x))
    }

    fn to_json(&self, py: Python<'_>) -> PyResult<String> {
        dumps(&self.json_value(py)?)
    }

    fn __richcmp__(&self, other: &Bound<'_, PyAny>, op: CompareOp, py: Python<'_>) -> Py<PyAny> {
        let Ok(other) = other.cast::<PyQuotientGroup>() else {
            return py.NotImplemented();
        };
        let equal = self.q.same_group(&other.get().q);
        match op {
            CompareOp::Eq => equal
                .into_pyobject(py)
                .expect("bool")
                .to_owned()
                .into_any()
                .unbind(),
            CompareOp::Ne => (!equal)
                .into_pyobject(py)
                .expect("bool")
                .to_owned()
                .into_any()
                .unbind(),
            _ => py.NotImplemented(),
        }
    }

    fn __hash__(&self) -> u64 {
        use std::hash::{DefaultHasher, Hash, Hasher};
        let mut h = DefaultHasher::new();
        (self.q.lifted(), self.q.n(), self.q.m()).hash(&mut h);
        h.finish()
    }

    fn __repr__(&self) -> String {
        let kind = if self.q.lifted() {
            "GL2QSubQuotient"
        } else {
            "GL2ASubQuotient"
        };
        format!("{kind}({}, {})", self.q.n(), self.q.m())
    }
}

#[pymethods]
impl PyGL2ASubQuotient {
    #[new]
    #[pyo3(signature = (N, M))]
    #[allow(non_snake_case)]
    fn new(
        py: Python<'_>,
        N: &Bound<'_, PyAny>,
        M: &Bound<'_, PyAny>,
    ) -> PyResult<PyClassInitializer<Self>> {
        let q = Quotient::new(parameter(py, N)?, parameter(py, M)?, false)
            .map_err(|err| to_pyerr(py, err))?;
        Ok(PyClassInitializer::from(PyQuotientGroup { q: Arc::new(q) })
            .add_subclass(PyGL2ASubQuotient))
    }

    fn to_lifted(slf: PyRef<'_, Self>, x: &Bound<'_, PyAny>) -> PyResult<PyQuotientElement> {
        let py = slf.py();
        let base = slf.as_super();
        let x = base.own(py, x)?;
        if !base.q.det_is_one(&x.u) {
            return Err(api_error(py, "NotInGroupError", "det u is not 1"));
        }
        let parent = new_parent(py, base.q.n(), base.q.m(), true)?;
        let q = parent.bind(py).cast::<PyQuotientGroup>()?.get().q.clone();
        Ok(PyQuotientElement { parent, q, x })
    }
}

#[pymethods]
impl PyGL2QSubQuotient {
    #[new]
    #[pyo3(signature = (N, M))]
    #[allow(non_snake_case)]
    fn new(
        py: Python<'_>,
        N: &Bound<'_, PyAny>,
        M: &Bound<'_, PyAny>,
    ) -> PyResult<PyClassInitializer<Self>> {
        let q = Quotient::new(parameter(py, N)?, parameter(py, M)?, true)
            .map_err(|err| to_pyerr(py, err))?;
        Ok(PyClassInitializer::from(PyQuotientGroup { q: Arc::new(q) })
            .add_subclass(PyGL2QSubQuotient))
    }

    fn from_matrix(slf: &Bound<'_, Self>, g: &Bound<'_, PyAny>) -> PyResult<PyQuotientElement> {
        let py = slf.py();
        let base = slf.cast::<PyQuotientGroup>()?;
        let x = base
            .get()
            .q
            .from_matrix(&matrix(g)?)
            .map_err(|err| to_pyerr(py, err))?;
        Ok(PyQuotientGroup::element(base, x))
    }

    fn to_adelic(slf: PyRef<'_, Self>, x: &Bound<'_, PyAny>) -> PyResult<PyQuotientElement> {
        let py = slf.py();
        let base = slf.as_super();
        let x = base.own(py, x)?;
        let parent = new_parent(py, base.q.n(), base.q.m(), false)?;
        let q = parent.bind(py).cast::<PyQuotientGroup>()?.get().q.clone();
        Ok(PyQuotientElement { parent, q, x })
    }
}

impl PyQuotientElement {
    fn with(&self, py: Python<'_>, x: Elem) -> PyQuotientElement {
        PyQuotientElement {
            parent: self.parent.clone_ref(py),
            q: self.q.clone(),
            x,
        }
    }
}

#[pymethods]
impl PyQuotientElement {
    fn parent(&self, py: Python<'_>) -> Py<PyAny> {
        self.parent.clone_ref(py)
    }

    fn coordinates(&self) -> (u64, (u64, u64, u64, u64)) {
        let [a, b, c, d] = self.x.u;
        (self.q.type_of(self.x.mask), (a, b, c, d))
    }

    fn r#type(&self) -> u64 {
        self.q.type_of(self.x.mask)
    }

    fn det(&self) -> u64 {
        self.q.det(&self.x.u)
    }

    fn order(&self, py: Python<'_>) -> PyResult<u64> {
        self.q
            .element_order(&self.x)
            .map_err(|err| to_pyerr(py, err))
    }

    fn inverse(&self, py: Python<'_>) -> PyQuotientElement {
        self.with(py, self.q.inverse(&self.x))
    }

    fn __mul__(&self, other: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let Ok(other) = other.cast::<PyQuotientElement>() else {
            return Ok(py.NotImplemented());
        };
        let other = other.get();
        if !other.q.same_group(&self.q) {
            return Err(api_error(
                py,
                "ParentMismatchError",
                "elements of different parents",
            ));
        }
        let product = self.with(py, self.q.mul(&self.x, &other.x));
        Ok(Py::new(py, product)?.into_any())
    }

    fn __pow__(
        &self,
        k: &Bound<'_, PyAny>,
        modulo: &Bound<'_, PyAny>,
        py: Python<'_>,
    ) -> PyResult<PyQuotientElement> {
        if !modulo.is_none() {
            return Err(PyTypeError::new_err(
                "pow() with a modulus is not supported",
            ));
        }
        let k = to_bigint(k)?;
        let x = self.q.pow(&self.x, &k).map_err(|err| to_pyerr(py, err))?;
        Ok(self.with(py, x))
    }

    fn __richcmp__(&self, other: &Bound<'_, PyAny>, op: CompareOp, py: Python<'_>) -> Py<PyAny> {
        let Ok(other) = other.cast::<PyQuotientElement>() else {
            return py.NotImplemented();
        };
        let other = other.get();
        let equal = self.q.same_group(&other.q) && self.x == other.x;
        match op {
            CompareOp::Eq => equal
                .into_pyobject(py)
                .expect("bool")
                .to_owned()
                .into_any()
                .unbind(),
            CompareOp::Ne => (!equal)
                .into_pyobject(py)
                .expect("bool")
                .to_owned()
                .into_any()
                .unbind(),
            _ => py.NotImplemented(),
        }
    }

    fn __hash__(&self) -> u64 {
        use std::hash::{DefaultHasher, Hash, Hasher};
        let mut h = DefaultHasher::new();
        (self.q.lifted(), self.q.n(), self.q.m(), self.x).hash(&mut h);
        h.finish()
    }

    fn __repr__(&self) -> String {
        let [a, b, c, d] = self.x.u;
        format!("({}, ({a}, {b}, {c}, {d}))", self.q.type_of(self.x.mask))
    }

    fn to_json(&self, py: Python<'_>) -> PyResult<String> {
        dumps(&element_json_value(py, &self.q, &self.x)?)
    }

    fn to_json_full(&self, py: Python<'_>) -> PyResult<String> {
        let d = PyDict::new(py);
        let parent = self
            .parent
            .bind(py)
            .cast::<PyQuotientGroup>()?
            .get()
            .json_value(py)?;
        d.set_item("parent", parent)?;
        d.set_item("element", element_json_value(py, &self.q, &self.x)?)?;
        dumps(&d.into_any())
    }
}

/// See `arithkit_api.modular.quotient.quotient_from_json`.
#[pyfunction]
pub fn quotient_from_json(py: Python<'_>, text: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    quotient_from_value(py, &loads(text)?)
}

/// The parent described by a decoded JSON value.
pub fn quotient_from_value(py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    let (kind, n, m): (String, Bound<'_, PyAny>, Bound<'_, PyAny>) = json_module(py)?
        .call_method1("decode_quotient", (value,))?
        .extract()?;
    new_parent(
        py,
        parameter(py, &n)?,
        parameter(py, &m)?,
        kind == "GL2QSubQuotient",
    )
}
