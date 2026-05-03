//! Semantic model for Python scope and binding analysis.
//!
//! The SemanticModel is immutable once created by the analyzer.

use pyo3::prelude::*;
use rustc_hash::{FxHashMap, FxHashSet};

use tree_sitter::Language;

use crate::analyzer::{
    AnnotationRef, Declaration, Redefinition, ShadowedImport, UnresolvedRef, UnusedBinding,
    UnusedDeclaration, UnusedName,
};
use crate::binding::Binding;
use crate::import_info::ImportInfo;
use crate::scope::Scope;

/// Per-line metadata computed from source bytes.
///
/// Replaces the old 13-element tuple with named fields for clarity.
/// Frozen: immutable after construction.
#[pyclass(frozen)]
pub struct LineInfo {
    #[pyo3(get)]
    pub leading_spaces: u16,
    #[pyo3(get)]
    pub indent_len: u16,
    #[pyo3(get)]
    pub line_len: u32,
    #[pyo3(get)]
    pub trailing_ws: u16,
    #[pyo3(get)]
    pub comment_start: i32,
    #[pyo3(get)]
    pub indent_has_tab: bool,
    #[pyo3(get)]
    pub indent_has_space: bool,
    #[pyo3(get)]
    pub is_blank: bool,
    #[pyo3(get)]
    pub is_in_string: bool,
    #[pyo3(get)]
    pub spaces_before_comment: i16,
    #[pyo3(get)]
    pub char_after_hash: u8,
    #[pyo3(get)]
    pub leading_hashes: u8,
    #[pyo3(get)]
    pub style_flags: u8,
}

// Ancestor context flags (bitfield)
pub const CTX_IN_LOOP: u16 = 1 << 0;
pub const CTX_IN_FUNCTION: u16 = 1 << 1;
pub const CTX_IN_CLASS: u16 = 1 << 2;
pub const CTX_IN_TRY: u16 = 1 << 3;
pub const CTX_IN_EXCEPT: u16 = 1 << 4;
pub const CTX_IN_FINALLY: u16 = 1 << 5;
pub const CTX_IN_WITH: u16 = 1 << 6;
pub const CTX_IN_LAMBDA: u16 = 1 << 7;
pub const CTX_IN_COMPREHENSION: u16 = 1 << 8;

/// Sentinel value for "no scope".
pub const NO_SCOPE: i64 = -1;

/// Arena-based semantic model for scope and binding analysis (immutable).
///
/// All scopes and bindings are stored in flat arrays indexed by their IDs.
/// The model is constructed entirely by the Rust analyzer and is read-only from Python.
#[pyclass(frozen)]
pub struct SemanticModel {
    // Core arenas - stored as Py<T> for Python interop
    pub scopes_vec: Vec<Py<Scope>>,
    pub bindings_vec: Vec<Py<Binding>>,

    // Language handle for lazy kind_id → &str conversion
    pub lang: Language,

    // Tracking lists for rule analysis
    pub unresolved_vec: Vec<Py<UnresolvedRef>>,
    pub annotation_only_vec: Vec<Py<AnnotationRef>>,
    pub declarations_vec: Vec<Py<Declaration>>,
    pub redefinitions_vec: Vec<Py<Redefinition>>,
    // Total AST node count
    pub node_count: usize,

    // Pre-computed unused bindings for F841/F401
    pub unused_variables_vec: Vec<Py<UnusedBinding>>,
    pub unused_imports_vec: Vec<Py<UnusedBinding>>,
    pub unused_annotations_vec: Vec<Py<UnusedName>>,
    pub unused_declarations_vec: Vec<Py<UnusedDeclaration>>,
    pub undefined_locals_vec: Vec<Py<UnusedName>>,
    pub shadowed_imports_vec: Vec<Py<ShadowedImport>>,

    // Ancestor context map: start_byte → (flags, loop_depth, function_depth)
    pub context_map: FxHashMap<usize, (u16, u8, u8)>,

    // Import metadata
    pub import_infos_vec: Vec<Py<ImportInfo>>,
    pub binding_import_map: FxHashMap<usize, usize>, // binding_id → import_info index

    // Pre-computed node_id → scope_index for O(1) scope_at_node_id
    pub node_id_to_scope: FxHashMap<i64, usize>,

    // 1-based line numbers inside multi-line strings (sorted, deduplicated)
    pub string_lines_vec: Vec<u32>,
    // noqa directives: line → None (blanket) or Some(codes)
    pub noqa_lines_map: FxHashMap<u32, Option<Vec<String>>>,
    // Per-line metadata (frozen pyclass with named fields).
    pub line_infos_vec: Vec<Py<LineInfo>>,

    // Pre-sorted scope intervals for O(log n) scope_for_position.
    // Each entry: (start_byte, end_byte, scope_idx), sorted by start_byte.
    pub scope_intervals: Vec<(usize, usize, usize)>,
}

impl SemanticModel {
    /// Walk the scope chain from `scope_id` upward, returning the first scope
    /// that satisfies `predicate`, or `None`.
    fn find_in_scope_chain(
        &self,
        py: Python<'_>,
        scope_id: i64,
        predicate: impl Fn(&Scope) -> bool,
    ) -> Option<i64> {
        let mut current = scope_id;
        while current != NO_SCOPE && (current as usize) < self.scopes_vec.len() {
            let scope = self.scopes_vec[current as usize].borrow(py);
            if predicate(&scope) {
                return Some(current);
            }
            current = scope.parent;
        }
        None
    }
}

#[pymethods]
impl SemanticModel {
    /// Get all scopes as a list for Python access.
    #[getter]
    fn scopes(&self, py: Python<'_>) -> Vec<Py<Scope>> {
        self.scopes_vec.iter().map(|s| s.clone_ref(py)).collect()
    }

    /// Get all bindings as a list for Python access.
    #[getter]
    fn bindings(&self, py: Python<'_>) -> Vec<Py<Binding>> {
        self.bindings_vec.iter().map(|b| b.clone_ref(py)).collect()
    }

    /// Get a single scope by index (avoids cloning the entire Vec).
    fn scope(&self, py: Python<'_>, id: usize) -> PyResult<Py<Scope>> {
        self.scopes_vec
            .get(id)
            .map(|s| s.clone_ref(py))
            .ok_or_else(|| pyo3::exceptions::PyIndexError::new_err("scope index out of range"))
    }

    /// Get a single binding by index (avoids cloning the entire Vec).
    fn binding(&self, py: Python<'_>, id: usize) -> PyResult<Py<Binding>> {
        self.bindings_vec
            .get(id)
            .map(|b| b.clone_ref(py))
            .ok_or_else(|| pyo3::exceptions::PyIndexError::new_err("binding index out of range"))
    }

    /// Get unresolved names for F821 checking.
    #[getter]
    fn unresolved(&self, py: Python<'_>) -> Vec<Py<UnresolvedRef>> {
        self.unresolved_vec
            .iter()
            .map(|r| r.clone_ref(py))
            .collect()
    }

    /// Get annotation-only declarations for F842 checking.
    #[getter]
    fn annotation_only(&self, py: Python<'_>) -> Vec<Py<AnnotationRef>> {
        self.annotation_only_vec
            .iter()
            .map(|r| r.clone_ref(py))
            .collect()
    }

    /// Get global/nonlocal declarations for F824 checking.
    #[getter]
    fn declarations(&self, py: Python<'_>) -> Vec<Py<Declaration>> {
        self.declarations_vec
            .iter()
            .map(|r| r.clone_ref(py))
            .collect()
    }

    /// Get redefinitions for F811 checking.
    #[getter]
    fn redefinitions(&self, py: Python<'_>) -> Vec<Py<Redefinition>> {
        self.redefinitions_vec
            .iter()
            .map(|r| r.clone_ref(py))
            .collect()
    }

    /// Get unused variables for F841 checking.
    #[getter]
    fn unused_variables(&self, py: Python<'_>) -> Vec<Py<UnusedBinding>> {
        self.unused_variables_vec
            .iter()
            .map(|r| r.clone_ref(py))
            .collect()
    }

    /// Get unused imports for F401 checking.
    #[getter]
    fn unused_imports(&self, py: Python<'_>) -> Vec<Py<UnusedBinding>> {
        self.unused_imports_vec
            .iter()
            .map(|r| r.clone_ref(py))
            .collect()
    }

    /// Get unused annotations for F842 checking.
    #[getter]
    fn unused_annotations(&self, py: Python<'_>) -> Vec<Py<UnusedName>> {
        self.unused_annotations_vec
            .iter()
            .map(|r| r.clone_ref(py))
            .collect()
    }

    /// Get unused declarations for F824 checking.
    #[getter]
    fn unused_declarations(&self, py: Python<'_>) -> Vec<Py<UnusedDeclaration>> {
        self.unused_declarations_vec
            .iter()
            .map(|r| r.clone_ref(py))
            .collect()
    }

    /// Get undefined locals for F823 checking.
    #[getter]
    fn undefined_locals(&self, py: Python<'_>) -> Vec<Py<UnusedName>> {
        self.undefined_locals_vec
            .iter()
            .map(|r| r.clone_ref(py))
            .collect()
    }

    /// Get shadowed imports for F402 checking.
    #[getter]
    fn shadowed_imports(&self, py: Python<'_>) -> Vec<Py<ShadowedImport>> {
        self.shadowed_imports_vec
            .iter()
            .map(|r| r.clone_ref(py))
            .collect()
    }

    /// Get the module scope ID (always 0 if scopes exist).
    #[getter]
    fn module_scope(&self) -> i64 {
        if self.scopes_vec.is_empty() {
            NO_SCOPE
        } else {
            0
        }
    }

    /// Look up a name starting from the given scope.
    #[pyo3(signature = (name, from_scope=None))]
    pub fn lookup(&self, py: Python<'_>, name: &str, from_scope: Option<i64>) -> Option<i64> {
        let mut scope_id = from_scope.unwrap_or(0);

        while scope_id != NO_SCOPE && (scope_id as usize) < self.scopes_vec.len() {
            let scope = self.scopes_vec[scope_id as usize].borrow(py);
            if let Some(&binding_id) = scope.bindings_map.get(name) {
                return Some(binding_id as i64);
            }
            scope_id = scope.parent;
        }

        None
    }

    /// Resolve a name from a given scope, respecting exception handler bounds.
    pub fn resolve_binding_from(
        &self,
        py: Python<'_>,
        name: &str,
        use_byte: usize,
        from_scope: i64,
    ) -> Option<i64> {
        let mut scope_id = from_scope;

        while scope_id != NO_SCOPE && (scope_id as usize) < self.scopes_vec.len() {
            let scope = self.scopes_vec[scope_id as usize].borrow(py);
            if let Some(&binding_id) = scope.bindings_map.get(name) {
                let binding = self.bindings_vec[binding_id].borrow(py);
                if let Some(valid_until) = binding.valid_until_byte
                    && use_byte >= valid_until
                {
                    scope_id = scope.parent;
                    continue;
                }
                return Some(binding_id as i64);
            }
            scope_id = scope.parent;
        }

        None
    }

    /// Check if a binding is used (has references).
    pub fn is_used(&self, py: Python<'_>, name: &str, scope_id: i64) -> bool {
        if scope_id == NO_SCOPE || (scope_id as usize) >= self.scopes_vec.len() {
            return false;
        }
        let scope = self.scopes_vec[scope_id as usize].borrow(py);

        if let Some(&binding_id) = scope.bindings_map.get(name) {
            let binding = self.bindings_vec[binding_id].borrow(py);
            !binding.references_vec.is_empty()
        } else {
            false
        }
    }

    /// Get the scope defined by a node (if it creates one) by its ID.
    pub fn scope_at_node_id(&self, _py: Python<'_>, node_id: i64) -> i64 {
        self.node_id_to_scope
            .get(&node_id)
            .map(|&idx| idx as i64)
            .unwrap_or(NO_SCOPE)
    }

    /// Get the scope defined by a node by its byte range.
    pub fn scope_at_position(&self, py: Python<'_>, start_byte: usize, end_byte: usize) -> i64 {
        for (i, scope) in self.scopes_vec.iter().enumerate() {
            let s = scope.borrow(py);
            if s.start_byte == start_byte && s.end_byte == end_byte {
                return i as i64;
            }
        }
        NO_SCOPE
    }

    /// Get the scope containing a position (smallest scope that contains the byte).
    ///
    /// Uses binary search to find candidate intervals, then exploits the
    /// monotonically increasing distance `byte_pos - start` to break early
    /// once no remaining interval can beat the current best.
    pub fn scope_for_position(&self, _py: Python<'_>, byte_pos: usize) -> i64 {
        let mut best: i64 = NO_SCOPE;
        let mut best_size = usize::MAX;

        // partition_point returns the first index where start > byte_pos,
        // so all intervals with start <= byte_pos are in [..idx].
        let idx = self
            .scope_intervals
            .partition_point(|&(start, _, _)| start <= byte_pos);

        // Walk backwards through candidates. Since intervals are sorted by
        // start ASC, `byte_pos - start` increases monotonically as we go
        // back. Once it exceeds best_size, any remaining interval must be
        // at least that large (its start is even smaller), so we can stop.
        for &(start, end, sid) in self.scope_intervals[..idx].iter().rev() {
            if byte_pos - start >= best_size {
                break;
            }
            if byte_pos >= end {
                continue;
            }
            let size = end - start;
            if size < best_size {
                best_size = size;
                best = sid as i64;
            }
        }
        best
    }

    /// Get the scope containing a node (compatibility wrapper for Node objects).
    /// Uses byte position for lookup since node IDs differ between parsers.
    pub fn scope_for(&self, py: Python<'_>, node: &Bound<'_, PyAny>) -> PyResult<i64> {
        let raw = node.getattr("raw")?;
        let start_byte: usize = raw.getattr("start_byte")?.extract()?;
        Ok(self.scope_for_position(py, start_byte))
    }

    /// Get the scope defined by a node (compatibility wrapper for Node objects).
    /// Uses byte range for lookup since node IDs differ between parsers.
    pub fn scope_at(&self, py: Python<'_>, node: &Bound<'_, PyAny>) -> PyResult<i64> {
        let raw = node.getattr("raw")?;
        let start_byte: usize = raw.getattr("start_byte")?.extract()?;
        let end_byte: usize = raw.getattr("end_byte")?.extract()?;
        Ok(self.scope_at_position(py, start_byte, end_byte))
    }

    /// Get the total number of nodes in the AST.
    #[getter]
    pub fn node_count(&self) -> usize {
        self.node_count
    }

    /// 1-based line numbers inside multi-line strings (sorted).
    #[getter]
    pub fn string_lines(&self) -> Vec<u32> {
        self.string_lines_vec.clone()
    }

    /// Mapping of line number to noqa codes (None = blanket noqa).
    #[getter]
    pub fn noqa_lines(&self) -> FxHashMap<u32, Option<Vec<String>>> {
        self.noqa_lines_map.clone()
    }

    /// Pre-computed metadata per line as a list of `LineInfo` structs.
    #[getter]
    pub fn line_infos(&self, py: Python<'_>) -> Vec<Py<LineInfo>> {
        self.line_infos_vec
            .iter()
            .map(|li| li.clone_ref(py))
            .collect()
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Scope chain helpers
    // ─────────────────────────────────────────────────────────────────────────

    /// Get the chain of scope IDs from the given scope up to the module scope.
    pub fn scope_chain(&self, py: Python<'_>, scope_id: i64) -> Vec<i64> {
        let mut chain = Vec::new();
        let mut current = scope_id;
        while current != NO_SCOPE && (current as usize) < self.scopes_vec.len() {
            chain.push(current);
            current = self.scopes_vec[current as usize].borrow(py).parent;
        }
        chain
    }

    /// Check if a scope is inside (or is) a function scope.
    pub fn is_in_function_scope(&self, py: Python<'_>, scope_id: i64) -> bool {
        self.find_in_scope_chain(py, scope_id, |s| s.type_ == crate::scope::SCOPE_FUNCTION)
            .is_some()
    }

    /// Check if a scope is inside (or is) a class scope.
    pub fn is_in_class_scope(&self, py: Python<'_>, scope_id: i64) -> bool {
        self.find_in_scope_chain(py, scope_id, |s| s.type_ == crate::scope::SCOPE_CLASS)
            .is_some()
    }

    /// Find the nearest enclosing scope of a given type.
    pub fn enclosing_scope(&self, py: Python<'_>, scope_id: i64, scope_type: u8) -> i64 {
        self.find_in_scope_chain(py, scope_id, |s| s.type_ == scope_type)
            .unwrap_or(NO_SCOPE)
    }

    /// Get all visible bindings from a scope (walking up the chain).
    /// Returns: Vec<(name, binding_id, scope_id)>
    pub fn visible_bindings(&self, py: Python<'_>, scope_id: i64) -> Vec<(String, usize, i64)> {
        let mut result = Vec::new();
        let mut seen: FxHashSet<String> = FxHashSet::default();
        let mut current = scope_id;
        while current != NO_SCOPE && (current as usize) < self.scopes_vec.len() {
            let scope = self.scopes_vec[current as usize].borrow(py);
            for (name, &binding_id) in &scope.bindings_map {
                if seen.insert(name.clone()) {
                    result.push((name.clone(), binding_id, current));
                }
            }
            current = scope.parent;
        }
        result
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Name usage queries
    // ─────────────────────────────────────────────────────────────────────────

    /// Check if a name was used between two lines in a given scope.
    pub fn has_use_between(
        &self,
        py: Python<'_>,
        name: &str,
        scope_id: i64,
        start_line: u32,
        end_line: u32,
    ) -> bool {
        if (scope_id as usize) >= self.scopes_vec.len() {
            return false;
        }
        let scope = self.scopes_vec[scope_id as usize].borrow(py);
        scope.uses_vec.iter().any(|(use_name, _, _, line, _)| {
            use_name == name && *line > start_line && *line < end_line
        })
    }

    /// Count uses of a name between two byte positions in a given scope.
    pub fn use_count_between(
        &self,
        py: Python<'_>,
        name: &str,
        scope_id: i64,
        start_byte: usize,
        end_byte: usize,
    ) -> usize {
        if (scope_id as usize) >= self.scopes_vec.len() {
            return 0;
        }
        let scope = self.scopes_vec[scope_id as usize].borrow(py);
        scope
            .uses_vec
            .iter()
            .filter(|(use_name, _, sb, _, _)| {
                use_name == name && *sb > start_byte && *sb < end_byte
            })
            .count()
    }

    /// Get all lines where a name is used in a given scope.
    pub fn use_lines(&self, py: Python<'_>, name: &str, scope_id: i64) -> Vec<u32> {
        if (scope_id as usize) >= self.scopes_vec.len() {
            return Vec::new();
        }
        let scope = self.scopes_vec[scope_id as usize].borrow(py);
        scope
            .uses_vec
            .iter()
            .filter(|(use_name, _, _, _, _)| use_name == name)
            .map(|(_, _, _, line, _)| *line)
            .collect()
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Ancestor context queries
    // ─────────────────────────────────────────────────────────────────────────

    /// Check if the node at start_byte is inside a loop.
    pub fn is_in_loop(&self, start_byte: usize) -> bool {
        self.has_context(start_byte, CTX_IN_LOOP)
    }

    /// Check if the node at start_byte is inside a function.
    pub fn is_in_function(&self, start_byte: usize) -> bool {
        self.has_context(start_byte, CTX_IN_FUNCTION)
    }

    /// Check if the node at start_byte has a specific context flag.
    pub fn has_context(&self, start_byte: usize, flag: u16) -> bool {
        self.context_map
            .get(&start_byte)
            .is_some_and(|(flags, _, _)| (flags & flag) != 0)
    }

    /// Get the full context for a node: (flags, loop_depth, function_depth).
    /// Returns None if the node has no context entry.
    pub fn node_context(&self, start_byte: usize) -> Option<(u16, u8, u8)> {
        self.context_map.get(&start_byte).copied()
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Import metadata queries
    // ─────────────────────────────────────────────────────────────────────────

    /// Get all import infos.
    pub fn imports(&self, py: Python<'_>) -> Vec<Py<ImportInfo>> {
        self.import_infos_vec
            .iter()
            .map(|i| i.clone_ref(py))
            .collect()
    }

    /// Get import info for a specific binding ID.
    pub fn import_info(&self, py: Python<'_>, binding_id: usize) -> Option<Py<ImportInfo>> {
        self.binding_import_map
            .get(&binding_id)
            .map(|&idx| self.import_infos_vec[idx].clone_ref(py))
    }

    /// Get all star imports.
    pub fn star_imports(&self, py: Python<'_>) -> Vec<Py<ImportInfo>> {
        self.import_infos_vec
            .iter()
            .filter(|i| i.borrow(py).is_star)
            .map(|i| i.clone_ref(py))
            .collect()
    }

    /// Get all __future__ imports.
    pub fn future_imports(&self, py: Python<'_>) -> Vec<Py<ImportInfo>> {
        self.import_infos_vec
            .iter()
            .filter(|i| i.borrow(py).is_future)
            .map(|i| i.clone_ref(py))
            .collect()
    }
}

// NOTE: All SemanticModel methods require Python<'_> or Py<T> objects,
// so Rust-native unit tests are not feasible without the PyO3 runtime.
// Scope lookup, binding resolution, and context queries are covered by
// the Python test suite in tests/ instead.
