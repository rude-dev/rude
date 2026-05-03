//! Vendored tree-sitter types exposed to Python via PyO3.
//!
//! Wraps tree-sitter's `Tree`, `Node`, and `TreeCursor` without lifetime
//! parameters by sharing ownership of the underlying tree through `Arc<TreeData>`.
//!
//! The `ffi::TSNode` / `ffi::TSTreeCursor` structs are `Copy` C types that
//! contain a raw pointer back into the tree. The `Arc<TreeData>` kept alive in
//! every wrapper guarantees that pointer stays valid.

use std::sync::Arc;

use pyo3::prelude::*;
use pyo3::types::PyBytes;
use tree_sitter::{Node, Parser, Tree, ffi};

// Compile-time check: transmute between ffi::TSNode and Node requires
// identical layout.  Node is #[repr(transparent)] over ffi::TSNode.
const _: () = {
    assert!(
        std::mem::size_of::<ffi::TSNode>() == std::mem::size_of::<Node<'static>>(),
        "ffi::TSNode and Node must have identical size"
    );
    assert!(
        std::mem::align_of::<ffi::TSNode>() == std::mem::align_of::<Node<'static>>(),
        "ffi::TSNode and Node must have identical alignment"
    );
};

// ─── Internal shared data ────────────────────────────────────────────────────

/// Shared ownership of the parsed tree and its source bytes.
///
/// Keeps a `Py<PyBytes>` alive (prevents GC) and caches the raw pointer
/// to the bytes buffer. Python `bytes` are immutable so the pointer is
/// valid for the lifetime of the `Py<PyBytes>`.
pub(crate) struct TreeData {
    pub tree: Tree,
    _source: Py<PyBytes>,
    source_ptr: *const u8,
    source_len: usize,
}

// SAFETY: TreeData is Send because:
// - `Py<PyBytes>` is Send (PyO3 guarantees this)
// - The raw `source_ptr` points into the PyBytes buffer, which is kept alive
//   by the `Py<PyBytes>` reference
// - `Tree` is Send in tree-sitter
unsafe impl Send for TreeData {}

// SAFETY: TreeData is Sync because:
// - `Py<PyBytes>` is Sync (PyO3 guarantees this)
// - `source_ptr` and `source_len` are read-only after construction
// - Python `bytes` objects are immutable, so the buffer cannot be modified
// - `Tree` is Sync in tree-sitter
unsafe impl Sync for TreeData {}

impl TreeData {
    /// Create from a parsed tree and a Python bytes object.
    fn new(tree: Tree, source: &Bound<'_, PyBytes>) -> Self {
        let bytes = source.as_bytes();
        TreeData {
            tree,
            _source: source.clone().unbind(),
            source_ptr: bytes.as_ptr(),
            source_len: bytes.len(),
        }
    }

    /// Create from a parsed tree and an already-owned `Py<PyBytes>`.
    ///
    /// Used by `batch_prepare` which creates the `Py<PyBytes>` on the GIL
    /// before releasing it for parallel work.
    pub(crate) fn from_owned(tree: Tree, source: Py<PyBytes>, ptr: *const u8, len: usize) -> Self {
        TreeData {
            tree,
            _source: source,
            source_ptr: ptr,
            source_len: len,
        }
    }

    /// Source bytes (no GIL needed).
    #[inline]
    pub fn source_bytes(&self) -> &[u8] {
        unsafe { std::slice::from_raw_parts(self.source_ptr, self.source_len) }
    }
}

// ─── TSTree ──────────────────────────────────────────────────────────────────

/// A parsed syntax tree.
#[pyclass(frozen)]
pub struct TSTree {
    pub(crate) data: Arc<TreeData>,
}

#[pymethods]
impl TSTree {
    /// Root node of the syntax tree.
    #[getter]
    fn root_node(&self) -> TSNode {
        TSNode::wrap(self.data.tree.root_node(), &self.data)
    }
}

// ─── TSNode ──────────────────────────────────────────────────────────────────

/// A single node in the syntax tree.
///
/// Stores a raw `ffi::TSNode` (a small `Copy` struct with a pointer into the
/// tree) plus an `Arc<TreeData>` that keeps the tree alive.
#[pyclass(frozen)]
pub struct TSNode {
    data: Arc<TreeData>,
    raw: ffi::TSNode,
}

// SAFETY: TSNode is Send because:
// - `ffi::TSNode` is a small Copy struct whose internal pointer points into the
//   tree-sitter arena, kept alive by `Arc<TreeData>`
// - `Arc<TreeData>` is Send
// - tree-sitter's `Node` is Send
unsafe impl Send for TSNode {}

// SAFETY: TSNode is Sync because:
// - `ffi::TSNode` is read-only (TSNode is #[pyclass(frozen)])
// - The tree-sitter arena it points into is immutable after parsing
// - `Arc<TreeData>` is Sync
// - tree-sitter's `Node` is Sync
unsafe impl Sync for TSNode {}

impl TSNode {
    /// Convert our stored `ffi::TSNode` back to a tree-sitter `Node<'_>`.
    ///
    /// Safety: `Node<'_>` is `#[repr(transparent)]` over `ffi::TSNode`.
    /// The `Arc<TreeData>` keeps the tree (and therefore all node pointers) alive.
    #[inline]
    fn node(&self) -> Node<'_> {
        unsafe { std::mem::transmute::<ffi::TSNode, Node<'_>>(self.raw) }
    }

    /// Wrap a tree-sitter `Node` into our `TSNode`, cloning the `Arc`.
    #[inline]
    pub(crate) fn wrap(node: Node, data: &Arc<TreeData>) -> Self {
        let raw = unsafe { std::mem::transmute::<Node<'_>, ffi::TSNode>(node) };
        TSNode {
            data: Arc::clone(data),
            raw,
        }
    }

    /// Wrap an `Option<Node>` — returns `None` for null nodes.
    #[inline]
    fn wrap_optional(node: Option<Node>, data: &Arc<TreeData>) -> Option<Self> {
        node.map(|n| Self::wrap(n, data))
    }
}

#[pymethods]
impl TSNode {
    // ── Identity & type ──────────────────────────────────────────────────

    /// Node type name (e.g. "function_definition", "identifier").
    #[getter]
    fn r#type(&self) -> &str {
        self.node().kind()
    }

    /// Node text as bytes.
    #[getter]
    fn text<'py>(&self, py: Python<'py>) -> Bound<'py, PyBytes> {
        let n = self.node();
        let slice = &self.data.source_bytes()[n.start_byte()..n.end_byte()];
        PyBytes::new(py, slice)
    }

    /// Unique node id within the tree.
    #[getter]
    fn id(&self) -> usize {
        self.node().id()
    }

    /// Whether this node is a named node.
    #[getter]
    fn is_named(&self) -> bool {
        self.node().is_named()
    }

    /// Whether this node is missing (inserted by error recovery).
    #[getter]
    fn is_missing(&self) -> bool {
        self.node().is_missing()
    }

    // ── Position ─────────────────────────────────────────────────────────

    /// Start position as `(row, column)` tuple (0-indexed).
    #[getter]
    fn start_point(&self) -> (usize, usize) {
        let p = self.node().start_position();
        (p.row, p.column)
    }

    /// End position as `(row, column)` tuple (0-indexed).
    #[getter]
    fn end_point(&self) -> (usize, usize) {
        let p = self.node().end_position();
        (p.row, p.column)
    }

    /// Byte offset where this node starts.
    #[getter]
    fn start_byte(&self) -> usize {
        self.node().start_byte()
    }

    /// Byte offset where this node ends.
    #[getter]
    fn end_byte(&self) -> usize {
        self.node().end_byte()
    }

    // ── Children ─────────────────────────────────────────────────────────

    /// Total child count (named + anonymous).
    #[getter]
    fn child_count(&self) -> usize {
        self.node().child_count()
    }

    /// Named child count.
    #[getter]
    fn named_child_count(&self) -> usize {
        self.node().named_child_count()
    }

    /// All children (including anonymous tokens).
    #[getter]
    fn children(&self) -> Vec<TSNode> {
        let node = self.node();
        let mut cursor = node.walk();
        node.children(&mut cursor)
            .map(|c| TSNode::wrap(c, &self.data))
            .collect()
    }

    /// Named children only.
    #[getter]
    fn named_children(&self) -> Vec<TSNode> {
        let node = self.node();
        let mut cursor = node.walk();
        node.named_children(&mut cursor)
            .map(|c| TSNode::wrap(c, &self.data))
            .collect()
    }

    // ── Navigation ───────────────────────────────────────────────────────

    /// Parent node, or `None` for root.
    #[getter]
    fn parent(&self) -> Option<TSNode> {
        TSNode::wrap_optional(self.node().parent(), &self.data)
    }

    /// Next sibling node.
    #[getter]
    fn next_sibling(&self) -> Option<TSNode> {
        TSNode::wrap_optional(self.node().next_sibling(), &self.data)
    }

    /// Previous sibling node.
    #[getter]
    fn prev_sibling(&self) -> Option<TSNode> {
        TSNode::wrap_optional(self.node().prev_sibling(), &self.data)
    }

    /// Child by field name.
    fn child_by_field_name(&self, name: &str) -> Option<TSNode> {
        TSNode::wrap_optional(self.node().child_by_field_name(name), &self.data)
    }

    /// All children with a given field name.
    fn children_by_field_name(&self, name: &str) -> Vec<TSNode> {
        let node = self.node();
        let mut cursor = node.walk();
        node.children_by_field_name(name, &mut cursor)
            .map(|c| TSNode::wrap(c, &self.data))
            .collect()
    }

    /// Create a `TSCursor` starting at this node.
    fn walk(&self) -> TSCursor {
        let raw = unsafe { ffi::ts_tree_cursor_new(self.raw) };
        TSCursor {
            data: Arc::clone(&self.data),
            raw,
        }
    }

    /// Smallest named descendant spanning the given byte range.
    fn descendant_for_byte_range(&self, start_byte: usize, end_byte: usize) -> Option<TSNode> {
        TSNode::wrap_optional(
            self.node().descendant_for_byte_range(start_byte, end_byte),
            &self.data,
        )
    }

    fn __repr__(&self) -> String {
        let n = self.node();
        format!(
            "<TSNode kind={} start={} end={}>",
            n.kind(),
            n.start_byte(),
            n.end_byte()
        )
    }
}

// ─── TSCursor ────────────────────────────────────────────────────────────────

/// A tree cursor for efficient traversal.
///
/// **Mutable** — not `frozen` because goto_* methods mutate the cursor.
#[pyclass]
pub struct TSCursor {
    data: Arc<TreeData>,
    raw: ffi::TSTreeCursor,
}

// SAFETY: TSCursor is Send because:
// - `ffi::TSTreeCursor` contains a pointer into the tree-sitter arena,
//   kept alive by `Arc<TreeData>`
// - `Arc<TreeData>` is Send
// - The cursor is only mutated through `&mut self` methods (goto_*)
unsafe impl Send for TSCursor {}

// SAFETY: TSCursor is Sync because PyO3 requires it for all #[pyclass] types.
// Although TSCursor has interior mutability (goto_* take &mut self), soundness
// is upheld by PyO3's runtime borrow checking: non-frozen pyclass instances are
// wrapped in a PyCell that enforces exclusive access at runtime, preventing
// concurrent &mut aliasing even under free-threaded Python (PEP 703).
unsafe impl Sync for TSCursor {}

impl Drop for TSCursor {
    fn drop(&mut self) {
        unsafe { ffi::ts_tree_cursor_delete(&mut self.raw) };
    }
}

#[pymethods]
impl TSCursor {
    /// Current node the cursor points to.
    #[getter]
    fn node(&self) -> TSNode {
        let raw_node = unsafe { ffi::ts_tree_cursor_current_node(&self.raw) };
        // Convert ffi::TSNode → Node → TSNode
        let node: Node<'_> = unsafe { std::mem::transmute(raw_node) };
        TSNode::wrap(node, &self.data)
    }

    /// Move to the first child. Returns `True` if the cursor moved.
    fn goto_first_child(&mut self) -> bool {
        unsafe { ffi::ts_tree_cursor_goto_first_child(&mut self.raw) }
    }

    /// Move to the next sibling. Returns `True` if the cursor moved.
    fn goto_next_sibling(&mut self) -> bool {
        unsafe { ffi::ts_tree_cursor_goto_next_sibling(&mut self.raw) }
    }

    /// Move to the parent. Returns `True` if the cursor moved.
    fn goto_parent(&mut self) -> bool {
        unsafe { ffi::ts_tree_cursor_goto_parent(&mut self.raw) }
    }
}

// ─── parse_python ────────────────────────────────────────────────────────────

/// Parse Python source bytes and return a `TSTree`.
///
/// Keeps a reference to the Python `bytes` object (zero-copy).
/// Uses a thread-local parser to avoid re-creating one on every call.
#[pyfunction]
pub fn parse_python(source: &Bound<'_, PyBytes>) -> PyResult<TSTree> {
    use std::cell::RefCell;

    thread_local! {
        static TL_PARSER: RefCell<Option<Parser>> = const { RefCell::new(None) };
    }

    let bytes = source.as_bytes();
    let lang: tree_sitter::Language = tree_sitter_python::LANGUAGE.into();

    let tree = TL_PARSER
        .with(|cell| {
            let mut borrow = cell.borrow_mut();
            let parser = borrow.get_or_insert_with(|| {
                let mut p = Parser::new();
                p.set_language(&lang).ok();
                p
            });
            parser.parse(bytes, None)
        })
        .ok_or_else(|| pyo3::exceptions::PyRuntimeError::new_err("Failed to parse source"))?;

    Ok(TSTree {
        data: Arc::new(TreeData::new(tree, source)),
    })
}
