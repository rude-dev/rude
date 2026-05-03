//! Rust implementation of rude's semantic model for high-performance scope analysis.
//!
//! This module provides a complete Python semantic analyzer implemented in Rust.
//! A single call to `analyze_source(bytes)` parses the source and builds an
//! immutable SemanticModel with all scopes, bindings, and references resolved.
//!
//! For lightweight AST grouping without semantic analysis, use `group_nodes()`.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock, mpsc};
use std::time::Duration;

use pyo3::prelude::*;
use pyo3::types::PyBytes;
use rayon::prelude::*;
use rustc_hash::{FxHashMap, FxHashSet};
use tree_sitter::{Node, Parser};

mod analyzer;
mod binding;
mod import_info;
mod model;
mod node_ids;
mod scope;
pub(crate) mod ts;

use analyzer::{AnalysisResult, RawGroups, RawNodeEntry, analyze_source, do_analyze_result};
use binding::Binding;
use model::{LineInfo, SemanticModel};
use scope::Scope;

/// Re-exports for criterion benchmarks. Not part of the public API.
#[doc(hidden)]
pub mod bench_api {
    pub use crate::analyzer::{
        AnalysisResult, RawGroups, RawLineInfo, compute_line_infos, compute_style_flags,
        do_analyze_result, find_comment_start_bytes,
    };
    pub use crate::collect_grouped_nodes;
}

/// Global rayon thread pool, created once and reused.
///
/// Reads `RUDE_RAYON_THREADS` env var to set thread count
/// (default: all CPUs via `available_parallelism`).
fn get_pool() -> PyResult<&'static rayon::ThreadPool> {
    static POOL: OnceLock<rayon::ThreadPool> = OnceLock::new();
    // OnceLock doesn't support fallible init, so we store the successful result
    // and handle the error on the first call only via a separate path.
    static INIT_ERR: OnceLock<String> = OnceLock::new();

    if let Some(pool) = POOL.get() {
        return Ok(pool);
    }

    let n = std::env::var("RUDE_RAYON_THREADS")
        .ok()
        .and_then(|s| s.parse::<usize>().ok())
        .unwrap_or_else(|| {
            std::thread::available_parallelism()
                .map(|n| n.get())
                .unwrap_or(4)
        })
        .clamp(1, 256);

    match rayon::ThreadPoolBuilder::new()
        .num_threads(n)
        .stack_size(4 * 1024 * 1024)
        .build()
    {
        Ok(pool) => {
            let _ = POOL.set(pool);
            Ok(POOL.get().unwrap())
        }
        Err(e) => {
            let msg = INIT_ERR.get_or_init(|| e.to_string());
            Err(pyo3::exceptions::PyRuntimeError::new_err(format!(
                "failed to create rayon thread pool: {msg}"
            )))
        }
    }
}

/// Rich node data exposed to Python as a frozen dataclass-like struct.
///
/// Replaces the old 11-element tuple in `GroupsDict`, giving Python code
/// named field access instead of positional indexing.
#[pyclass(frozen)]
pub struct NodeEntry {
    #[pyo3(get)]
    pub start_byte: usize,
    #[pyo3(get)]
    pub end_byte: usize,
    #[pyo3(get)]
    pub start_row: u32,
    #[pyo3(get)]
    pub start_col: u32,
    #[pyo3(get)]
    pub end_row: u32,
    #[pyo3(get)]
    pub end_col: u32,
    #[pyo3(get)]
    pub parent_type: Option<String>,
    #[pyo3(get)]
    pub named_child_count: u32,
    #[pyo3(get)]
    pub child_count: u32,
    #[pyo3(get)]
    pub first_child_type: Option<String>,
    #[pyo3(get)]
    pub last_child_type: Option<String>,
}

/// Recursively collect rich node data grouped by type, without scope analysis.
#[allow(clippy::only_used_in_recursion)]
pub fn collect_grouped_nodes(
    node: Node,
    parent_kind_id: u16,
    lang: &tree_sitter::Language,
    filter_set: &Option<FxHashSet<u16>>,
    groups: &mut RawGroups,
) {
    let kind_id = node.kind_id();

    let include = match filter_set {
        None => true,
        Some(set) => set.contains(&kind_id),
    };

    if include {
        let end_pos = node.end_position();
        let child_count = node.child_count() as u32;
        let first_child_kind_id = node.child(0).map_or(0, |c| c.kind_id());
        let last_child_kind_id = if child_count > 1 {
            node.child(child_count as usize - 1)
                .map_or(0, |c| c.kind_id())
        } else {
            first_child_kind_id
        };

        groups.entry(kind_id).or_default().push(RawNodeEntry {
            start_byte: node.start_byte(),
            end_byte: node.end_byte(),
            start_row: node.start_position().row as u32 + 1,
            start_col: node.start_position().column as u32,
            end_row: end_pos.row as u32 + 1,
            end_col: end_pos.column as u32,
            parent_kind: parent_kind_id,
            named_child_count: node.named_child_count() as u32,
            child_count,
            first_child_kind: first_child_kind_id,
            last_child_kind: last_child_kind_id,
        });
    }

    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        collect_grouped_nodes(child, kind_id, lang, filter_set, groups);
    }
}

/// Intern a kind_id to its string name, caching the result.
#[inline]
fn intern_kind(
    kid: u16,
    lang: &tree_sitter::Language,
    cache: &mut FxHashMap<u16, String>,
) -> String {
    cache
        .entry(kid)
        .or_insert_with(|| lang.node_kind_for_id(kid).unwrap_or("unknown").to_string())
        .clone()
}

/// Intern a kind_id to Option<String> (None for 0 = no node).
#[inline]
fn opt_intern_kind(
    kid: u16,
    lang: &tree_sitter::Language,
    cache: &mut FxHashMap<u16, String>,
) -> Option<String> {
    if kid == 0 {
        None
    } else {
        Some(intern_kind(kid, lang, cache))
    }
}

/// Build a filter set from node-type names, returning `None` when unfiltered.
fn build_filter_set(
    lang: &tree_sitter::Language,
    filter_types: &[String],
) -> Option<FxHashSet<u16>> {
    if filter_types.is_empty() {
        return None;
    }
    Some(
        filter_types
            .iter()
            .filter_map(|name| {
                let id = lang.id_for_node_kind(name, true);
                (id != 0).then_some(id)
            })
            .collect(),
    )
}

/// Convert raw u16-keyed groups to String-keyed `GroupsDict`, interning kind names.
fn convert_raw_groups(
    py: Python<'_>,
    raw_groups: RawGroups,
    lang: &tree_sitter::Language,
    kind_cache: &mut FxHashMap<u16, String>,
) -> PyResult<GroupsDict> {
    raw_groups
        .into_iter()
        .map(|(kid, entries)| {
            let type_name = intern_kind(kid, lang, kind_cache);
            let converted = entries
                .into_iter()
                .map(|e| {
                    Py::new(
                        py,
                        NodeEntry {
                            start_byte: e.start_byte,
                            end_byte: e.end_byte,
                            start_row: e.start_row,
                            start_col: e.start_col,
                            end_row: e.end_row,
                            end_col: e.end_col,
                            parent_type: opt_intern_kind(e.parent_kind, lang, kind_cache),
                            named_child_count: e.named_child_count,
                            child_count: e.child_count,
                            first_child_type: opt_intern_kind(e.first_child_kind, lang, kind_cache),
                            last_child_type: opt_intern_kind(e.last_child_kind, lang, kind_cache),
                        },
                    )
                })
                .collect::<PyResult<Vec<_>>>()?;
            Ok((type_name, converted))
        })
        .collect()
}

/// Core grouping logic: group nodes from a root into a dict.
fn do_group_nodes(
    py: Python<'_>,
    root: Node,
    lang: &tree_sitter::Language,
    filter_types: &[String],
) -> PyResult<GroupsDict> {
    let filter_set = build_filter_set(lang, filter_types);

    let mut raw_groups: RawGroups = FxHashMap::default();
    collect_grouped_nodes(root, 0, lang, &filter_set, &mut raw_groups);

    let mut kind_cache: FxHashMap<u16, String> = FxHashMap::default();
    convert_raw_groups(py, raw_groups, lang, &mut kind_cache)
}

/// Group nodes by type without scope analysis.
///
/// Accepts either raw `source` bytes or a pre-parsed `TSTree`.
#[pyfunction]
#[pyo3(signature = (source, filter_types, *, tree=None))]
pub fn group_nodes(
    py: Python<'_>,
    source: &[u8],
    filter_types: Vec<String>,
    tree: Option<&ts::TSTree>,
) -> PyResult<GroupsDict> {
    let lang: tree_sitter::Language = tree_sitter_python::LANGUAGE.into();

    if let Some(ts_tree) = tree {
        return do_group_nodes(py, ts_tree.data.tree.root_node(), &lang, &filter_types);
    }

    let mut parser = Parser::new();
    parser.set_language(&lang).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("Failed to set language: {e}"))
    })?;

    let parsed = parser
        .parse(source, None)
        .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Failed to parse source"))?;

    do_group_nodes(py, parsed.root_node(), &lang, &filter_types)
}

/// Type alias for batch_analyze results (path, source, tree, model, groups).
type BatchAnalyzeItem = (String, Py<PyBytes>, ts::TSTree, SemanticModel, GroupsDict);

/// Type alias for the grouped-nodes dict returned to Python.
type GroupsDict = FxHashMap<String, Vec<Py<NodeEntry>>>;

// ─── analyze_and_group ───────────────────────────────────────────────────────

/// Analyze source and group nodes in a single AST traversal.
///
/// Combines analyze_source + group_nodes to avoid double traversal.
/// Accepts a pre-parsed TSTree, returns (SemanticModel, GroupsDict).
#[pyfunction]
fn analyze_and_group(
    py: Python<'_>,
    tree: &ts::TSTree,
    filter_types: Vec<String>,
) -> PyResult<(SemanticModel, GroupsDict)> {
    let lang: tree_sitter::Language = tree_sitter_python::LANGUAGE.into();
    let filter_set = build_filter_set(&lang, &filter_types);

    // Release the GIL for the pure-Rust analysis phase.
    let data = tree.data.clone();
    let mut result = py.detach(|| {
        let root = data.tree.root_node();
        let source = data.source_bytes();
        do_analyze_result(source, root, &filter_set)
    });

    let raw_groups = result.take_groups();
    let model = result.into_model(py)?;

    let mut kind_cache: FxHashMap<u16, String> = FxHashMap::default();
    let groups = convert_raw_groups(py, raw_groups, &lang, &mut kind_cache)?;

    Ok((model, groups))
}

// ─── find_comment_start ──────────────────────────────────────────────────────

/// Find the byte-offset of a `#` comment in a Python line, ignoring `#` inside
/// string literals.  Returns -1 when the line has no comment.
#[pyfunction]
fn find_comment_start(line: &str) -> i32 {
    crate::analyzer::find_comment_start_bytes(line.as_bytes())
}

// ─── Streaming batch iterator ────────────────────────────────────────────────

type RawResult = (String, Vec<u8>, tree_sitter::Tree, AnalysisResult);

/// Streaming iterator over batch analysis results.
///
/// Backed by a bounded `sync_channel(8)` — rayon workers send results through
/// the channel, Python consumes one at a time via `__next__`. Only ~8 buffered
/// Rust results + 1 Python result exist at any time, keeping memory low.
#[pyclass]
struct BatchAnalyzeIter {
    receiver: Option<Mutex<mpsc::Receiver<RawResult>>>,
    lang: tree_sitter::Language,
    kind_cache: FxHashMap<u16, String>,
    cancel: Arc<AtomicBool>,
    _handle: Option<std::thread::JoinHandle<()>>,
}

#[pymethods]
impl BatchAnalyzeIter {
    fn __iter__(slf: PyRef<Self>) -> PyRef<Self> {
        slf
    }

    fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<BatchAnalyzeItem>> {
        let receiver = match self.receiver.as_ref() {
            Some(m) => m.lock().map_err(|_| {
                pyo3::exceptions::PyRuntimeError::new_err("batch receiver lock poisoned")
            })?,
            None => return Ok(None),
        };
        loop {
            match receiver.recv_timeout(Duration::from_millis(100)) {
                Ok((path, raw_bytes, tree, result)) => {
                    let py_bytes = PyBytes::new(py, &raw_bytes);
                    let py_bytes_owned: Py<PyBytes> = py_bytes.clone().unbind();
                    let ptr = py_bytes.as_bytes().as_ptr();
                    let len = py_bytes.as_bytes().len();

                    let ts_tree = ts::TSTree {
                        data: Arc::new(ts::TreeData::from_owned(
                            tree,
                            py_bytes_owned.clone_ref(py),
                            ptr,
                            len,
                        )),
                    };

                    let mut result = result;
                    let raw_groups = result.take_groups();
                    let model = result.into_model(py)?;

                    let groups =
                        convert_raw_groups(py, raw_groups, &self.lang, &mut self.kind_cache)?;

                    return Ok(Some((path, py_bytes_owned, ts_tree, model, groups)));
                }
                Err(mpsc::RecvTimeoutError::Timeout) => {
                    py.check_signals()?;
                }
                Err(mpsc::RecvTimeoutError::Disconnected) => {
                    return Ok(None);
                }
            }
        }
    }
}

impl Drop for BatchAnalyzeIter {
    fn drop(&mut self) {
        self.cancel.store(true, Ordering::Relaxed);
        // Drop receiver so all blocked senders get Err immediately
        drop(self.receiver.take());
        if let Some(h) = self._handle.take() {
            let _ = h.join();
        }
    }
}

/// Create a streaming iterator that analyzes files in parallel via rayon.
///
/// Yields one result at a time through a bounded channel, keeping
/// memory usage constant regardless of file count.
#[pyfunction]
fn batch_analyze_iter(
    _py: Python<'_>,
    paths: Vec<String>,
    filter_types: Vec<String>,
) -> PyResult<BatchAnalyzeIter> {
    let lang: tree_sitter::Language = tree_sitter_python::LANGUAGE.into();

    // Validate the pool early so we return a proper PyErr instead of panicking
    // inside the spawned thread.
    get_pool()?;

    let filter_set = Arc::new(build_filter_set(&lang, &filter_types));

    let (tx, rx) = mpsc::sync_channel::<RawResult>(8);
    let cancel = Arc::new(AtomicBool::new(false));
    let cancel_clone = cancel.clone();
    let thread_lang = lang.clone();

    let handle = std::thread::spawn(move || {
        // get_pool() cannot fail here: if it failed during __new__, we wouldn't reach this point.
        // Use expect() since this is inside a spawned thread (not across FFI).
        get_pool().expect("rayon pool already validated").install(|| {
        // Thread-local parser: created once per rayon thread, reused across files
        std::thread_local! {
            static TL_PARSER: std::cell::RefCell<Option<Parser>> = const { std::cell::RefCell::new(None) };
        }
        paths.par_iter().for_each_with(tx, |tx, path| {
            if cancel_clone.load(Ordering::Relaxed) {
                return;
            }

            let Ok(bytes) = std::fs::read(path) else { return };
            let tree = TL_PARSER.with(|cell| {
                let mut borrow = cell.borrow_mut();
                let parser = borrow.get_or_insert_with(|| {
                    let mut p = Parser::new();
                    p.set_language(&thread_lang).ok();
                    p
                });
                parser.parse(&bytes, None)
            });
            let Some(tree) = tree else { return };

            // Analyze + group in a single AST traversal (filter_set shared via Arc)
            let result = do_analyze_result(&bytes, tree.root_node(), &filter_set);

            if tx.send((path.clone(), bytes, tree, result)).is_err() {
                cancel_clone.store(true, Ordering::Relaxed);
            }
        });
        }); // pool.install
    });

    Ok(BatchAnalyzeIter {
        receiver: Some(Mutex::new(rx)),
        lang,
        kind_cache: FxHashMap::default(),
        cancel,
        _handle: Some(handle),
    })
}

/// Return all named node-type strings from tree-sitter-python's grammar.
///
/// Queries `Language::node_kind_count()` and filters to named kinds only,
/// providing the canonical set for Python-side validation.
#[pyfunction]
fn node_type_names() -> Vec<&'static str> {
    let lang: tree_sitter::Language = tree_sitter_python::LANGUAGE.into();
    let count = lang.node_kind_count();
    let mut names = Vec::new();
    for id in 0..count as u16 {
        if lang.node_kind_is_named(id)
            && let Some(name) = lang.node_kind_for_id(id)
            && !name.starts_with('_')
        {
            names.push(name);
        }
    }
    names
}

/// Python module for rude semantic analysis.
///
/// Exports:
/// - analyze_source: Main entry point - parses source and returns SemanticModel
/// - SemanticModel: Immutable semantic model with scopes/bindings
/// - Scope: Scope data (immutable)
/// - Binding: Binding data (immutable)
/// - Constants: NO_SCOPE, SCOPE_*, FLAG_*
#[pymodule(name = "_rust")]
fn rude_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Main entry points
    m.add_function(wrap_pyfunction!(analyze_source, m)?)?;
    m.add_function(wrap_pyfunction!(group_nodes, m)?)?;
    m.add_function(wrap_pyfunction!(ts::parse_python, m)?)?;
    m.add_function(wrap_pyfunction!(batch_analyze_iter, m)?)?;
    m.add_function(wrap_pyfunction!(analyze_and_group, m)?)?;
    m.add_function(wrap_pyfunction!(find_comment_start, m)?)?;
    m.add_function(wrap_pyfunction!(node_type_names, m)?)?;

    // Core classes
    m.add_class::<NodeEntry>()?;
    m.add_class::<BatchAnalyzeIter>()?;
    m.add_class::<Scope>()?;
    m.add_class::<Binding>()?;
    m.add_class::<SemanticModel>()?;
    m.add_class::<LineInfo>()?;
    m.add_class::<import_info::ImportInfo>()?;

    // Semantic analysis result classes
    m.add_class::<analyzer::UnresolvedRef>()?;
    m.add_class::<analyzer::AnnotationRef>()?;
    m.add_class::<analyzer::Declaration>()?;
    m.add_class::<analyzer::Redefinition>()?;
    m.add_class::<analyzer::NameUse>()?;
    m.add_class::<analyzer::UnusedBinding>()?;
    m.add_class::<analyzer::UnusedName>()?;
    m.add_class::<analyzer::UnusedDeclaration>()?;
    m.add_class::<analyzer::ShadowedImport>()?;

    // Tree-sitter types
    m.add_class::<ts::TSTree>()?;
    m.add_class::<ts::TSNode>()?;
    m.add_class::<ts::TSCursor>()?;

    // Sentinel constant
    m.add("NO_SCOPE", model::NO_SCOPE)?;

    // ScopeType enum values
    m.add("SCOPE_MODULE", scope::SCOPE_MODULE)?;
    m.add("SCOPE_CLASS", scope::SCOPE_CLASS)?;
    m.add("SCOPE_FUNCTION", scope::SCOPE_FUNCTION)?;
    m.add("SCOPE_COMPREHENSION", scope::SCOPE_COMPREHENSION)?;

    // BindingFlags enum values
    m.add("FLAG_IMPORT", binding::FLAG_IMPORT)?;
    m.add("FLAG_PARAMETER", binding::FLAG_PARAMETER)?;
    m.add("FLAG_GLOBAL", binding::FLAG_GLOBAL)?;
    m.add("FLAG_NONLOCAL", binding::FLAG_NONLOCAL)?;
    m.add("FLAG_EXCEPTION", binding::FLAG_EXCEPTION)?;

    // Ancestor context flags
    m.add("CTX_IN_LOOP", model::CTX_IN_LOOP)?;
    m.add("CTX_IN_FUNCTION", model::CTX_IN_FUNCTION)?;
    m.add("CTX_IN_CLASS", model::CTX_IN_CLASS)?;
    m.add("CTX_IN_TRY", model::CTX_IN_TRY)?;
    m.add("CTX_IN_EXCEPT", model::CTX_IN_EXCEPT)?;
    m.add("CTX_IN_FINALLY", model::CTX_IN_FINALLY)?;
    m.add("CTX_IN_WITH", model::CTX_IN_WITH)?;
    m.add("CTX_IN_LAMBDA", model::CTX_IN_LAMBDA)?;
    m.add("CTX_IN_COMPREHENSION", model::CTX_IN_COMPREHENSION)?;

    Ok(())
}
