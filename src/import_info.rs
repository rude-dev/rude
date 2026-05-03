//! Import metadata for semantic analysis.
//!
//! ImportInfo captures detailed information about each import statement,
//! enabling rules to analyze import patterns without re-parsing the AST.

use pyo3::prelude::*;

/// Detailed metadata about a single import.
#[pyclass(frozen)]
pub struct ImportInfo {
    /// Binding ID for this import (-1 for star imports which have no named binding).
    #[pyo3(get)]
    pub binding_id: i64,

    /// Module being imported from (e.g., "os", "os.path", "__future__").
    #[pyo3(get)]
    pub module: String,

    /// Original name before aliasing (e.g., "path" in "from os import path as p").
    #[pyo3(get)]
    pub original_name: String,

    /// Whether this is a star import (`from X import *`).
    #[pyo3(get)]
    pub is_star: bool,

    /// Whether this import uses an alias.
    #[pyo3(get)]
    pub is_aliased: bool,

    /// Whether this is a `from __future__` import.
    #[pyo3(get)]
    pub is_future: bool,

    /// Whether this is a relative import.
    #[pyo3(get)]
    pub is_relative: bool,

    /// Whether this is a `from X import Y` style import.
    #[pyo3(get)]
    pub is_from_import: bool,

    /// Scope ID in which this import appears.
    #[pyo3(get)]
    pub scope_id: i64,

    /// Line number of the import statement.
    #[pyo3(get)]
    pub line: u32,

    /// Column of the import statement.
    #[pyo3(get)]
    pub column: u32,
}

impl ImportInfo {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        binding_id: i64,
        module: String,
        original_name: String,
        is_star: bool,
        is_aliased: bool,
        is_future: bool,
        is_relative: bool,
        is_from_import: bool,
        scope_id: i64,
        line: u32,
        column: u32,
    ) -> Self {
        ImportInfo {
            binding_id,
            module,
            original_name,
            is_star,
            is_aliased,
            is_future,
            is_relative,
            is_from_import,
            scope_id,
            line,
            column,
        }
    }
}
