//! Scope data structure for semantic analysis.
//!
//! Scopes are immutable once created by the analyzer.

use pyo3::prelude::*;
use rustc_hash::{FxHashMap, FxHashSet};

use crate::analyzer::NameUse;

/// Scope type constants matching Python ScopeType enum.
pub const SCOPE_MODULE: u8 = 1;
pub const SCOPE_CLASS: u8 = 2;
pub const SCOPE_FUNCTION: u8 = 3;
pub const SCOPE_COMPREHENSION: u8 = 4;

/// Scope data stored in arena (immutable after construction).
#[pyclass(frozen)]
pub struct Scope {
    #[pyo3(get)]
    pub type_: u8,

    #[pyo3(get)]
    pub node_id: i64,

    #[pyo3(get)]
    pub parent: i64,

    // Byte range for position-based lookup (start_byte, end_byte)
    #[pyo3(get)]
    pub start_byte: usize,

    #[pyo3(get)]
    pub end_byte: usize,

    // Owned data (frozen - no interior mutability needed)
    pub bindings_map: FxHashMap<String, usize>,
    pub globals_set: FxHashSet<String>,
    pub nonlocals_set: FxHashSet<String>,
    pub children_vec: Vec<i64>,
    // uses: (name, node_id, start_byte, line, column)
    pub uses_vec: Vec<(String, i64, usize, u32, u32)>,
}

impl Scope {
    /// Create a scope with all data pre-populated (used by analyzer).
    #[allow(clippy::too_many_arguments)]
    pub fn with_data(
        type_: u8,
        node_id: i64,
        parent: i64,
        start_byte: usize,
        end_byte: usize,
        bindings: FxHashMap<String, usize>,
        globals: FxHashSet<String>,
        nonlocals: FxHashSet<String>,
        children: Vec<i64>,
        uses: Vec<(String, i64, usize, u32, u32)>,
    ) -> Self {
        Scope {
            type_,
            node_id,
            parent,
            start_byte,
            end_byte,
            bindings_map: bindings,
            globals_set: globals,
            nonlocals_set: nonlocals,
            children_vec: children,
            uses_vec: uses,
        }
    }
}

#[pymethods]
impl Scope {
    /// Scope type as an integer (see ``ScopeType`` enum).
    #[getter]
    #[pyo3(name = "type")]
    fn get_type(&self) -> u8 {
        self.type_
    }

    /// Get the bindings dict for Python access.
    #[getter]
    fn bindings(&self) -> FxHashMap<String, usize> {
        self.bindings_map.clone()
    }

    /// Get globals set for Python access.
    #[getter]
    fn globals(&self) -> FxHashSet<String> {
        self.globals_set.clone()
    }

    /// Get nonlocals set for Python access.
    #[getter]
    fn nonlocals(&self) -> FxHashSet<String> {
        self.nonlocals_set.clone()
    }

    /// Get children list for Python access.
    #[getter]
    fn children(&self) -> Vec<i64> {
        self.children_vec.clone()
    }

    /// Get uses list for Python access.
    #[getter]
    fn uses(&self, py: Python<'_>) -> PyResult<Vec<Py<NameUse>>> {
        self.uses_vec
            .iter()
            .map(|(name, node_id, start_byte, line, col)| {
                Py::new(
                    py,
                    NameUse {
                        name: name.clone(),
                        node_id: *node_id,
                        start_byte: *start_byte,
                        line: *line,
                        column: *col,
                    },
                )
            })
            .collect()
    }
}
