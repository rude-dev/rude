//! Binding data structure for semantic analysis.
//!
//! Bindings are immutable once created by the analyzer.

use pyo3::prelude::*;

/// Binding flag constants matching Python BindingFlags enum.
pub const FLAG_IMPORT: u8 = 1;
pub const FLAG_PARAMETER: u8 = 2;
pub const FLAG_GLOBAL: u8 = 4;
pub const FLAG_NONLOCAL: u8 = 8;
pub const FLAG_EXCEPTION: u8 = 16;

/// Binding data stored in arena (immutable after construction).
///
/// Represents a variable binding with its location, scope, and usage information.
#[pyclass(frozen)]
pub struct Binding {
    #[pyo3(get)]
    pub name: String,

    #[pyo3(get)]
    pub node_id: i64,

    #[pyo3(get)]
    pub start_byte: usize,

    #[pyo3(get)]
    pub end_byte: usize,

    #[pyo3(get)]
    pub line: u32,

    #[pyo3(get)]
    pub column: u32,

    #[pyo3(get)]
    pub scope: i64,

    #[pyo3(get)]
    pub flags: u8,

    #[pyo3(get)]
    pub valid_until_byte: Option<usize>,

    // Owned references list (frozen - populated during analysis)
    pub references_vec: Vec<i64>,

    // Pre-computed usage flag (set during model construction)
    #[pyo3(get)]
    pub is_used: bool,
}

impl Binding {
    /// Create a binding with references pre-populated (used by analyzer).
    /// The `is_used` flag is computed from whether references is non-empty.
    #[allow(clippy::too_many_arguments)]
    pub fn with_references(
        name: String,
        node_id: i64,
        start_byte: usize,
        end_byte: usize,
        line: u32,
        column: u32,
        scope: i64,
        flags: u8,
        valid_until_byte: Option<usize>,
        references: Vec<i64>,
    ) -> Self {
        let is_used = !references.is_empty();
        Binding {
            name,
            node_id,
            start_byte,
            end_byte,
            line,
            column,
            scope,
            flags,
            valid_until_byte,
            references_vec: references,
            is_used,
        }
    }
}

#[pymethods]
impl Binding {
    /// Get references list for Python access.
    #[getter]
    fn references(&self) -> Vec<i64> {
        self.references_vec.clone()
    }

    /// Check if this binding is an import.
    #[getter]
    fn is_import(&self) -> bool {
        (self.flags & FLAG_IMPORT) != 0
    }

    /// Check if this binding is a function parameter.
    #[getter]
    fn is_parameter(&self) -> bool {
        (self.flags & FLAG_PARAMETER) != 0
    }

    /// Check if this binding has global declaration.
    #[getter]
    fn is_global(&self) -> bool {
        (self.flags & FLAG_GLOBAL) != 0
    }

    /// Check if this binding has nonlocal declaration.
    #[getter]
    fn is_nonlocal(&self) -> bool {
        (self.flags & FLAG_NONLOCAL) != 0
    }

    /// Check if this binding is an exception handler variable.
    #[getter]
    fn is_exception_handler(&self) -> bool {
        (self.flags & FLAG_EXCEPTION) != 0
    }
}
