//! Bindings of `arithkit_core::modular::subgroup`; see `arithkit_api.modular.subgroup`.

use std::sync::Arc;

use arithkit_core::modular::quotient::{Elem, Quotient};
use arithkit_core::modular::subgroup::Subgroup;
use pyo3::basic::CompareOp;
use pyo3::exceptions::PyTypeError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};

use crate::convert::{api_error, dumps, json_module, loads, to_pyerr};
use crate::modular::quotient::{
    PyQuotientElement, PyQuotientGroup, element_from_value, element_json_value, quotient_from_value,
};

/// A subgroup; see `arithkit_api.modular.subgroup.QuotientSubgroup`.
#[pyclass(name = "QuotientSubgroup", module = "arithkit._native", frozen)]
pub struct PyQuotientSubgroup {
    pub parent: Py<PyAny>,
    pub q: Arc<Quotient>,
    pub sub: Arc<Subgroup>,
}

impl PyQuotientSubgroup {
    fn element(&self, py: Python<'_>, x: Elem) -> PyQuotientElement {
        PyQuotientElement {
            parent: self.parent.clone_ref(py),
            q: self.q.clone(),
            x,
        }
    }

    fn tuple_of<'py>(&self, py: Python<'py>, els: &[Elem]) -> PyResult<Bound<'py, PyTuple>> {
        let objs = els
            .iter()
            .map(|x| Bound::new(py, self.element(py, *x)))
            .collect::<PyResult<Vec<_>>>()?;
        PyTuple::new(py, objs)
    }
}

#[pymethods]
impl PyQuotientSubgroup {
    fn parent(&self, py: Python<'_>) -> Py<PyAny> {
        self.parent.clone_ref(py)
    }

    fn order(&self) -> usize {
        self.sub.order()
    }

    fn index<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let order = py
            .import("builtins")?
            .call_method1("int", (self.q.order().to_hex(), 16))?;
        order.call_method1("__floordiv__", (self.sub.order(),))
    }

    fn elements<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyTuple>> {
        self.tuple_of(py, self.sub.elements())
    }

    fn gens<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyTuple>> {
        self.tuple_of(py, self.sub.gens())
    }

    fn al_image<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyTuple>> {
        PyTuple::new(py, self.sub.al_image(&self.q))
    }

    fn is_subgroup_of(&self, other: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<bool> {
        let other = other
            .cast::<PyQuotientSubgroup>()
            .map_err(|_| PyTypeError::new_err("expected a native QuotientSubgroup"))?
            .get();
        if !other.q.same_group(&self.q) {
            return Err(api_error(
                py,
                "ParentMismatchError",
                "subgroups of different parents",
            ));
        }
        Ok(self.sub.is_subset(&other.sub))
    }

    fn __contains__(&self, x: &Bound<'_, PyAny>) -> bool {
        match x.cast::<PyQuotientElement>() {
            Ok(el) => {
                let el = el.get();
                el.q.same_group(&self.q) && self.sub.contains(&el.x)
            }
            Err(_) => false,
        }
    }

    fn __richcmp__(&self, other: &Bound<'_, PyAny>, op: CompareOp, py: Python<'_>) -> Py<PyAny> {
        let Ok(other) = other.cast::<PyQuotientSubgroup>() else {
            return py.NotImplemented();
        };
        let other = other.get();
        let equal = self.q.same_group(&other.q) && *self.sub == *other.sub;
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
        (self.q.lifted(), self.q.n(), self.q.m(), self.sub.gens()).hash(&mut h);
        h.finish()
    }

    fn __repr__(&self) -> String {
        let kind = if self.q.lifted() {
            "LiftedQuotient"
        } else {
            "AdelicQuotient"
        };
        format!(
            "subgroup of order {} of {kind}({}, {})",
            self.sub.order(),
            self.q.n(),
            self.q.m()
        )
    }

    fn to_json(&self, py: Python<'_>) -> PyResult<String> {
        let kind = if self.q.lifted() {
            "LiftedQuotient"
        } else {
            "AdelicQuotient"
        };
        let parent =
            json_module(py)?.call_method1("encode_quotient", (kind, self.q.n(), self.q.m()))?;
        let gens = PyList::empty(py);
        for g in self.sub.gens() {
            gens.append(element_json_value(py, &self.q, g)?)?;
        }
        let d = PyDict::new(py);
        d.set_item("parent", parent)?;
        d.set_item("gens", gens)?;
        dumps(&d.into_any())
    }
}

/// See `arithkit_api.modular.subgroup.subgroup_from_json`.
#[pyfunction]
pub fn subgroup_from_json(py: Python<'_>, text: &Bound<'_, PyAny>) -> PyResult<PyQuotientSubgroup> {
    let (parent_value, gen_values): (Bound<'_, PyAny>, Vec<Bound<'_, PyAny>>) = json_module(py)?
        .call_method1("decode_subgroup", (loads(text)?,))?
        .extract()?;
    let parent = quotient_from_value(py, &parent_value)?;
    let q = parent.bind(py).cast::<PyQuotientGroup>()?.get().q.clone();
    let gens = gen_values
        .iter()
        .map(|v| element_from_value(py, &q, v))
        .collect::<PyResult<Vec<_>>>()?;
    let sub = Subgroup::generated(&q, &gens).map_err(|err| to_pyerr(py, err))?;
    Ok(PyQuotientSubgroup {
        parent,
        q,
        sub: Arc::new(sub),
    })
}
