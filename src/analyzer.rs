//! Full AST analyzer for Python source code.
//!
//! This module parses Python source and traverses the AST entirely in Rust,
//! building the SemanticModel without any Python calls.

use pyo3::prelude::*;
use rustc_hash::{FxHashMap, FxHashSet};
use tree_sitter::{Language, Node, Parser};

use crate::ts::TSTree;

use crate::binding::{
    Binding, FLAG_EXCEPTION, FLAG_GLOBAL, FLAG_IMPORT, FLAG_NONLOCAL, FLAG_PARAMETER,
};
use crate::import_info::ImportInfo;
use crate::model::{
    CTX_IN_CLASS, CTX_IN_COMPREHENSION, CTX_IN_EXCEPT, CTX_IN_FINALLY, CTX_IN_FUNCTION,
    CTX_IN_LAMBDA, CTX_IN_LOOP, CTX_IN_TRY, CTX_IN_WITH, LineInfo, NO_SCOPE, SemanticModel,
};
use crate::node_ids::{FieldIds, NodeKinds};
use crate::scope::{SCOPE_CLASS, SCOPE_COMPREHENSION, SCOPE_FUNCTION, SCOPE_MODULE, Scope};

/// 1-based line number from a tree-sitter Node.
pub(crate) fn node_line(node: Node) -> u32 {
    node.start_position().row as u32 + 1
}

/// 0-based column offset from a tree-sitter Node.
pub(crate) fn node_col(node: Node) -> u32 {
    node.start_position().column as u32
}

/// O(1) containment check via byte ranges.
fn contains_node(container: Node, target: Node) -> bool {
    target.start_byte() >= container.start_byte() && target.end_byte() <= container.end_byte()
}

/// Find the first descendant of `node` with the given kind ID.
fn find_first<'b>(node: Node<'b>, kind_id: u16) -> Option<Node<'b>> {
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        if child.kind_id() == kind_id {
            return Some(child);
        }
        if let Some(result) = find_first(child, kind_id) {
            return Some(result);
        }
    }
    None
}

/// Find all descendants of `node` with the given kind ID.
fn find_all<'b>(node: Node<'b>, kind_id: u16) -> Vec<Node<'b>> {
    let mut result = Vec::new();
    find_all_into(node, kind_id, &mut result);
    result
}

fn find_all_into<'b>(node: Node<'b>, kind_id: u16, result: &mut Vec<Node<'b>>) {
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        if child.kind_id() == kind_id {
            result.push(child);
        }
        find_all_into(child, kind_id, result);
    }
}

// ─── Named structs replacing internal tuples ────────────────────────────────

/// An unresolved name reference (F821).
#[pyclass(frozen)]
pub struct UnresolvedRef {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub node_id: i64,
    #[pyo3(get)]
    pub start_byte: usize,
    #[pyo3(get)]
    pub line: u32,
    #[pyo3(get)]
    pub column: u32,
    #[pyo3(get)]
    pub scope_id: i64,
}

/// An annotation-only declaration (F842).
#[pyclass(frozen)]
pub struct AnnotationRef {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub node_id: i64,
    #[pyo3(get)]
    pub start_byte: usize,
    #[pyo3(get)]
    pub line: u32,
    #[pyo3(get)]
    pub column: u32,
    #[pyo3(get)]
    pub scope_id: i64,
}

/// A global/nonlocal declaration (F824).
#[pyclass(frozen)]
pub struct Declaration {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub node_id: i64,
    #[pyo3(get)]
    pub start_byte: usize,
    #[pyo3(get)]
    pub line: u32,
    #[pyo3(get)]
    pub column: u32,
    #[pyo3(get)]
    pub scope_id: i64,
    #[pyo3(get)]
    pub is_global: bool,
}

/// A redefinition record (F811).
#[pyclass(frozen)]
pub struct Redefinition {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub scope_id: i64,
    #[pyo3(get)]
    pub new_line: u32,
    #[pyo3(get)]
    pub new_column: u32,
    #[pyo3(get)]
    pub old_line: u32,
}

/// A name use within a scope.
#[pyclass(frozen)]
pub struct NameUse {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub node_id: i64,
    #[pyo3(get)]
    pub start_byte: usize,
    #[pyo3(get)]
    pub line: u32,
    #[pyo3(get)]
    pub column: u32,
}

/// An unused binding for F841 (unused vars) and F401 (unused imports).
#[pyclass(frozen)]
pub struct UnusedBinding {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub line: u32,
    #[pyo3(get)]
    pub column: u32,
    #[pyo3(get)]
    pub start_byte: usize,
    #[pyo3(get)]
    pub end_byte: usize,
    #[pyo3(get)]
    pub scope_id: i64,
}

/// An unused name for F842 (unused annotations) and F823 (undefined locals).
#[pyclass(frozen)]
pub struct UnusedName {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub line: u32,
    #[pyo3(get)]
    pub column: u32,
}

/// An unused global/nonlocal declaration for F824.
#[pyclass(frozen)]
pub struct UnusedDeclaration {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub line: u32,
    #[pyo3(get)]
    pub column: u32,
    #[pyo3(get)]
    pub is_global: bool,
}

/// A shadowed import for F402.
#[pyclass(frozen)]
pub struct ShadowedImport {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub loop_line: u32,
    #[pyo3(get)]
    pub loop_column: u32,
    #[pyo3(get)]
    pub import_line: u32,
}

// ─────────────────────────────────────────────────────────────────────────────

/// Information extracted from a name node (collected before mutation).
struct NameInfo {
    name: String,
    node_id: i64,
    start_byte: usize,
    end_byte: usize,
    line: u32,
    column: u32,
}

impl NameInfo {
    fn from_node(node: Node, source: &[u8]) -> Self {
        let text = &source[node.start_byte()..node.end_byte()];
        NameInfo {
            name: String::from_utf8_lossy(text).into_owned(),
            node_id: node.id() as i64,
            start_byte: node.start_byte(),
            end_byte: node.end_byte(),
            line: node_line(node),
            column: node_col(node),
        }
    }
}

/// Raw node entry before conversion to Python-facing NodeEntry.
pub struct RawNodeEntry {
    pub start_byte: usize,
    pub end_byte: usize,
    pub start_row: u32,
    pub start_col: u32,
    pub end_row: u32,
    pub end_col: u32,
    pub parent_kind: u16,
    pub named_child_count: u32,
    pub child_count: u32,
    pub first_child_kind: u16,
    pub last_child_kind: u16,
}

/// Raw grouped node data keyed by kind_id.
pub type RawGroups = FxHashMap<u16, Vec<RawNodeEntry>>;

/// Per-line metadata computed from source bytes.
#[derive(Clone)]
pub struct RawLineInfo {
    pub leading_spaces: u16,
    pub indent_len: u16,
    pub line_len: u32,
    pub trailing_ws: u16,
    pub comment_start: i32,
    pub indent_has_tab: bool,
    pub indent_has_space: bool,
    pub is_blank: bool,
    pub is_in_string: bool,
    pub spaces_before_comment: i16,
    pub char_after_hash: u8,
    pub leading_hashes: u8,
    pub style_flags: u8,
}

/// Find the byte-offset of a `#` comment in a line of bytes, ignoring `#`
/// inside string literals. Returns -1 when no comment is found.
pub fn find_comment_start_bytes(line: &[u8]) -> i32 {
    let len = line.len();
    let mut i = 0;
    let mut in_string = false;
    let mut string_char: u8 = 0;

    while i < len {
        let c = line[i];
        if in_string {
            if c == b'\\' && i + 1 < len {
                i += 2;
                continue;
            }
            if c == string_char {
                in_string = false;
            }
        } else if c == b'"' || c == b'\'' {
            if i + 2 < len && line[i + 1] == c && line[i + 2] == c {
                let mut j = i + 3;
                while j + 2 < len {
                    if line[j] == c && line[j + 1] == c && line[j + 2] == c {
                        i = j + 3;
                        break;
                    }
                    j += 1;
                }
                if j + 2 >= len {
                    return -1;
                }
                continue;
            }
            in_string = true;
            string_char = c;
        } else if c == b'#' {
            return i as i32;
        }
        i += 1;
    }
    -1
}

/// Maximum AST nesting depth the analyzer will recurse into.
///
/// Protects against adversarial input that could otherwise cause a stack
/// overflow. Typical Python files have depth well under 50; 500 leaves
/// enormous headroom for generated code.
const MAX_ANALYZE_DEPTH: u32 = 500;

// Style flag bits for early-reject optimization in Python LineRules.
const STYLE_DOUBLE_SPACE_AROUND_OP: u8 = 0x01;
const STYLE_TAB_AROUND_OP: u8 = 0x02;
const STYLE_DOUBLE_SPACE_AFTER_COMMA: u8 = 0x04;
const STYLE_TAB_AFTER_COMMA: u8 = 0x08;
const STYLE_DOUBLE_SPACE_AROUND_KW: u8 = 0x10;
const STYLE_TAB_AROUND_KW: u8 = 0x20;

/// Operator characters: [-+*/%@&|^<>=!]
#[inline]
fn is_op_char(b: u8) -> bool {
    matches!(
        b,
        b'-' | b'+' | b'*' | b'/' | b'%' | b'@' | b'&' | b'|' | b'^' | b'<' | b'>' | b'=' | b'!'
    )
}

/// Check if byte is an identifier character (a-z, A-Z, 0-9, _).
#[inline]
fn is_ident(b: u8) -> bool {
    b.is_ascii_alphanumeric() || b == b'_'
}

/// The 31 keywords to detect for E271/E272/E273/E274.
const KEYWORDS: &[&[u8]] = &[
    b"and",
    b"or",
    b"not",
    b"in",
    b"is",
    b"if",
    b"elif",
    b"else",
    b"for",
    b"while",
    b"with",
    b"as",
    b"try",
    b"except",
    b"finally",
    b"return",
    b"yield",
    b"import",
    b"from",
    b"def",
    b"class",
    b"lambda",
    b"raise",
    b"assert",
    b"global",
    b"nonlocal",
    b"pass",
    b"break",
    b"continue",
    b"async",
    b"await",
];

/// Skip past a string literal starting at position `i` in `code`.
/// Handles single/double quotes, triple-quoted strings, and backslash escapes.
/// Returns the index after the closing quote(s), or `code.len()` if unterminated.
fn skip_string(code: &[u8], i: usize) -> usize {
    let len = code.len();
    let q = code[i]; // b'\'' or b'"'

    // Check for triple-quote
    if i + 2 < len && code[i + 1] == q && code[i + 2] == q {
        let mut j = i + 3;
        while j + 2 < len {
            if code[j] == b'\\' {
                j += 2;
                continue;
            }
            if code[j] == q && code[j + 1] == q && code[j + 2] == q {
                return j + 3;
            }
            j += 1;
        }
        return len; // unterminated triple-quote on this line
    }

    // Single-quoted string
    let mut j = i + 1;
    while j < len {
        if code[j] == b'\\' {
            j += 2;
            continue;
        }
        if code[j] == q {
            return j + 1;
        }
        j += 1;
    }
    len // unterminated
}

/// Compute style hint flags for a code portion of a line (bytes before comment).
///
/// The flags are optimization hints — false positives are OK, false negatives are not.
/// Each bit indicates a particular whitespace anomaly might exist on the line.
pub fn compute_style_flags(code: &[u8]) -> u8 {
    let len = code.len();
    if len == 0 {
        return 0;
    }

    let mut flags: u8 = 0;
    let mut i: usize = 0;

    while i < len {
        let b = code[i];

        // Skip string literals
        if b == b'\'' || b == b'"' {
            i = skip_string(code, i);
            continue;
        }

        // Check operators: is there 2+ spaces or a tab adjacent to an operator char?
        if is_op_char(b) {
            // Check before the operator
            if i > 0 {
                if code[i - 1] == b'\t' {
                    flags |= STYLE_TAB_AROUND_OP;
                } else if i >= 2 && code[i - 1] == b' ' && code[i - 2] == b' ' {
                    flags |= STYLE_DOUBLE_SPACE_AROUND_OP;
                }
            }
            // Check after the operator: find the end of the operator sequence
            let mut end = i + 1;
            while end < len && is_op_char(code[end]) {
                end += 1;
            }
            if end < len {
                if code[end] == b'\t' {
                    flags |= STYLE_TAB_AROUND_OP;
                } else if end + 1 < len && code[end] == b' ' && code[end + 1] == b' ' {
                    flags |= STYLE_DOUBLE_SPACE_AROUND_OP;
                }
            }
            i = end;
            continue;
        }

        // Check comma/semicolon: is there 2+ spaces or a tab after?
        if b == b',' || b == b';' {
            if i + 1 < len {
                if code[i + 1] == b'\t' {
                    flags |= STYLE_TAB_AFTER_COMMA;
                } else if i + 2 < len && code[i + 1] == b' ' && code[i + 2] == b' ' {
                    flags |= STYLE_DOUBLE_SPACE_AFTER_COMMA;
                }
            }
            i += 1;
            continue;
        }

        // Check keywords at word boundaries
        if b.is_ascii_alphabetic() {
            // Check if we're at a word boundary (no ident char before)
            if i > 0 && is_ident(code[i - 1]) {
                // Not a word boundary — skip to end of identifier
                while i < len && is_ident(code[i]) {
                    i += 1;
                }
                continue;
            }

            // Try to match any keyword
            let mut matched_kw_end: Option<usize> = None;
            for kw in KEYWORDS {
                let kw_len = kw.len();
                if i + kw_len <= len && &code[i..i + kw_len] == *kw {
                    // Check word boundary after keyword
                    if i + kw_len >= len || !is_ident(code[i + kw_len]) {
                        matched_kw_end = Some(i + kw_len);
                        break;
                    }
                }
            }

            if let Some(kw_end) = matched_kw_end {
                // Check for 2+ spaces or tab BEFORE the keyword
                if i > 0 {
                    if code[i - 1] == b'\t' {
                        flags |= STYLE_TAB_AROUND_KW;
                    } else if i >= 2 && code[i - 1] == b' ' && code[i - 2] == b' ' {
                        flags |= STYLE_DOUBLE_SPACE_AROUND_KW;
                    }
                }
                // Check for 2+ spaces or tab AFTER the keyword
                if kw_end < len {
                    if code[kw_end] == b'\t' {
                        flags |= STYLE_TAB_AROUND_KW;
                    } else if kw_end + 1 < len && code[kw_end] == b' ' && code[kw_end + 1] == b' ' {
                        flags |= STYLE_DOUBLE_SPACE_AROUND_KW;
                    }
                }
                i = kw_end;
                continue;
            }

            // Not a keyword — skip identifier
            while i < len && is_ident(code[i]) {
                i += 1;
            }
            continue;
        }

        i += 1;
    }

    flags
}

/// Compute per-line metadata from source bytes in a single pass.
pub fn compute_line_infos(source: &[u8], string_lines: &FxHashSet<u32>) -> Vec<RawLineInfo> {
    let len = source.len();
    // Estimate line count for pre-allocation
    let est_lines = source.iter().filter(|&&b| b == b'\n').count() + 1;
    let mut result = Vec::with_capacity(est_lines);
    let mut pos = 0;

    while pos < len {
        let line_start = pos;

        // Find end of line (before newline)
        while pos < len && source[pos] != b'\n' && source[pos] != b'\r' {
            pos += 1;
        }
        let line_end = pos;

        // Skip newline chars
        if pos < len {
            if source[pos] == b'\r' {
                pos += 1;
                if pos < len && source[pos] == b'\n' {
                    pos += 1;
                }
            } else {
                pos += 1; // \n
            }
        }

        let line = &source[line_start..line_end];
        let line_len = line.len() as u32;

        // Scan leading whitespace
        let mut leading_spaces: u16 = 0;
        let mut indent_has_tab = false;
        let mut indent_has_space = false;
        let mut i = 0;

        // Count contiguous spaces from position 0
        while i < line.len() && line[i] == b' ' {
            leading_spaces += 1;
            i += 1;
        }
        if leading_spaces > 0 {
            indent_has_space = true;
        }

        // Continue scanning rest of leading whitespace
        while i < line.len() && (line[i] == b' ' || line[i] == b'\t') {
            if line[i] == b' ' {
                indent_has_space = true;
            } else {
                indent_has_tab = true;
            }
            i += 1;
        }

        let indent_len = i as u16;
        let is_blank = i == line.len();

        // Count trailing whitespace
        let mut trailing_ws: u16 = 0;
        let mut j = line.len();
        while j > 0 && (line[j - 1] == b' ' || line[j - 1] == b'\t') {
            trailing_ws += 1;
            j -= 1;
        }

        let comment_start = find_comment_start_bytes(line);

        let (spaces_before_comment, char_after_hash, leading_hashes): (i16, u8, u8) =
            if comment_start >= 0 {
                let cs = comment_start as usize;

                // spaces_before_comment: -1 if block comment (no code before #)
                let sbc = if cs == 0 {
                    -1i16
                } else {
                    let before = &line[..cs];
                    let trimmed_len = before
                        .iter()
                        .rposition(|&b| b != b' ' && b != b'\t')
                        .map(|p| p + 1)
                        .unwrap_or(0);
                    if trimmed_len == 0 {
                        -1i16 // only whitespace before #
                    } else {
                        (cs - trimmed_len) as i16
                    }
                };

                // Count consecutive # from comment_start
                let mut h = cs;
                let mut hash_count: u8 = 0;
                while h < line.len() && line[h] == b'#' {
                    hash_count += 1;
                    h += 1;
                }
                let cah = if h < line.len() { line[h] } else { 0u8 };

                (sbc, cah, hash_count)
            } else {
                (-1i16, 0u8, 0u8)
            };

        let line_number = result.len() as u32 + 1; // 1-based

        // Compute style flags on the code portion (before comment)
        let is_in_string = string_lines.contains(&line_number);
        let style_flags = if is_in_string || is_blank {
            0u8
        } else {
            let code_end = if comment_start >= 0 {
                comment_start as usize
            } else {
                line.len()
            };
            compute_style_flags(&line[..code_end])
        };

        result.push(RawLineInfo {
            leading_spaces,
            indent_len,
            line_len,
            trailing_ws,
            comment_start,
            indent_has_tab,
            indent_has_space,
            is_blank,
            is_in_string,
            spaces_before_comment,
            char_after_hash,
            leading_hashes,
            style_flags,
        });
    }

    // Handle empty file (no lines processed)
    if result.is_empty() && len == 0 {
        result.push(RawLineInfo {
            leading_spaces: 0,
            indent_len: 0,
            line_len: 0,
            trailing_ws: 0,
            comment_start: -1,
            indent_has_tab: false,
            indent_has_space: false,
            is_blank: true,
            is_in_string: false,
            spaces_before_comment: -1,
            char_after_hash: 0,
            leading_hashes: 0,
            style_flags: 0,
        });
    }

    result
}

/// Owned analysis result — Send, no lifetimes, no GIL required.
/// Enables rayon parallelism: analyze in parallel, then convert on GIL.
#[allow(private_interfaces)]
pub struct AnalysisResult {
    pub lang: Language,
    pub scopes: Vec<ScopeBuilder>,
    pub bindings: Vec<BindingBuilder>,
    pub unresolved: Vec<UnresolvedRef>,
    pub annotation_only: Vec<AnnotationRef>,
    pub declarations: Vec<Declaration>,
    pub redefinitions: Vec<Redefinition>,
    pub node_count: usize,
    pub for_loop_bindings: Vec<(String, u32, u32)>,
    pub context_map: FxHashMap<usize, (u16, u8, u8)>,
    pub import_infos: Vec<ImportInfo>,
    pub binding_import_map: FxHashMap<usize, usize>,
    pub dunder_all_names: FxHashSet<String>,
    /// 1-based line numbers inside multi-line strings (for E111, E703).
    pub string_lines: Vec<u32>,
    /// noqa directives: line → None (blanket) or Some(codes).
    pub noqa_lines: FxHashMap<u32, Option<Vec<String>>>,
    /// Grouped node data collected during the same AST traversal.
    pub raw_groups: Option<RawGroups>,
    /// Per-line metadata computed from source bytes.
    pub line_infos: Vec<RawLineInfo>,
}

/// Mutable scope data during analysis.
pub(crate) struct ScopeBuilder {
    pub type_: u8,
    pub node_id: i64,
    pub parent: i64,
    pub start_byte: usize,
    pub end_byte: usize,
    pub bindings: FxHashMap<String, usize>,
    pub globals: FxHashSet<String>,
    pub nonlocals: FxHashSet<String>,
    pub children: Vec<i64>,
    pub uses: Vec<NameUse>,
}

impl ScopeBuilder {
    fn new(type_: u8, node_id: i64, parent: i64, start_byte: usize, end_byte: usize) -> Self {
        ScopeBuilder {
            type_,
            node_id,
            parent,
            start_byte,
            end_byte,
            bindings: FxHashMap::default(),
            globals: FxHashSet::default(),
            nonlocals: FxHashSet::default(),
            children: Vec::new(),
            uses: Vec::new(),
        }
    }
}

/// Mutable binding data during analysis.
pub(crate) struct BindingBuilder {
    pub name: String,
    pub node_id: i64,
    pub start_byte: usize,
    pub end_byte: usize,
    pub line: u32,
    pub column: u32,
    pub scope: i64,
    pub flags: u8,
    pub valid_until_byte: Option<usize>,
    pub references: Vec<i64>,
}

impl BindingBuilder {
    #[allow(clippy::too_many_arguments)]
    fn new(
        name: String,
        node_id: i64,
        start_byte: usize,
        end_byte: usize,
        line: u32,
        column: u32,
        scope: i64,
        flags: u8,
        valid_until_byte: Option<usize>,
    ) -> Self {
        BindingBuilder {
            name,
            node_id,
            start_byte,
            end_byte,
            line,
            column,
            scope,
            flags,
            valid_until_byte,
            references: Vec::new(),
        }
    }
}

/// The analyzer that builds a SemanticModel from Python source.
struct Analyzer<'a, 'f> {
    source: &'a [u8],
    nk: NodeKinds,
    fk: FieldIds,
    lang: Language,
    scopes: Vec<ScopeBuilder>,
    bindings: Vec<BindingBuilder>,
    scope_stack: Vec<i64>,
    unresolved: Vec<UnresolvedRef>,
    annotation_only: Vec<AnnotationRef>,
    declarations: Vec<Declaration>,
    redefinitions: Vec<Redefinition>,
    node_count: usize,
    /// For-loop variable bindings: (name, line, col) - for F402 shadowed import check
    for_loop_bindings: Vec<(String, u32, u32)>,
    // Ancestor context tracking
    loop_depth: u8,
    function_depth: u8,
    context_flags: u16,
    /// Sparse context map: start_byte → (flags, loop_depth, function_depth)
    context_map: FxHashMap<usize, (u16, u8, u8)>,
    // Import metadata
    import_infos: Vec<ImportInfo>,
    /// Maps binding_id → index in import_infos
    binding_import_map: FxHashMap<usize, usize>,
    /// Names listed in module-level `__all__`
    dunder_all_names: FxHashSet<String>,
    /// 1-based line numbers inside multi-line strings.
    string_lines: Vec<u32>,
    /// noqa directives: line → None (blanket) or Some(codes).
    noqa_lines: FxHashMap<u32, Option<Vec<String>>>,
    /// Grouped node data collected during the same AST traversal.
    raw_groups: RawGroups,
    /// Filter set for grouped nodes (None = collect all).
    group_filter: &'f Option<FxHashSet<u16>>,
}

impl<'a, 'f> Analyzer<'a, 'f> {
    fn new(source: &'a [u8], lang: Language, group_filter: &'f Option<FxHashSet<u16>>) -> Self {
        let nk = NodeKinds::new(&lang);
        let fk = FieldIds::new(&lang).expect("tree-sitter-python field IDs");
        Analyzer {
            source,
            nk,
            fk,
            lang,
            scopes: Vec::new(),
            bindings: Vec::new(),
            scope_stack: Vec::new(),
            unresolved: Vec::new(),
            annotation_only: Vec::new(),
            declarations: Vec::new(),
            redefinitions: Vec::new(),
            node_count: 0,
            for_loop_bindings: Vec::new(),
            loop_depth: 0,
            function_depth: 0,
            context_flags: 0,
            context_map: FxHashMap::default(),
            import_infos: Vec::new(),
            binding_import_map: FxHashMap::default(),
            dunder_all_names: FxHashSet::default(),
            string_lines: Vec::new(),
            noqa_lines: FxHashMap::default(),
            raw_groups: FxHashMap::default(),
            group_filter,
        }
    }

    fn current_scope(&self) -> i64 {
        self.scope_stack.last().copied().unwrap_or(NO_SCOPE)
    }

    fn push_scope(&mut self, kind: u8, node_id: i64, start_byte: usize, end_byte: usize) -> i64 {
        let scope_id = self.scopes.len() as i64;
        let parent = self.current_scope();

        self.scopes.push(ScopeBuilder::new(
            kind, node_id, parent, start_byte, end_byte,
        ));

        if parent != NO_SCOPE {
            self.scopes[parent as usize].children.push(scope_id);
        }

        self.scope_stack.push(scope_id);
        scope_id
    }

    fn pop_scope(&mut self) {
        self.scope_stack.pop();
    }

    #[allow(clippy::too_many_arguments)]
    fn add_binding(
        &mut self,
        name: String,
        node_id: i64,
        start_byte: usize,
        end_byte: usize,
        line: u32,
        column: u32,
        flags: u8,
        valid_until_byte: Option<usize>,
        target_scope: Option<i64>,
    ) -> usize {
        let binding_id = self.bindings.len();
        let scope_id = target_scope.unwrap_or_else(|| self.current_scope());

        // F811: if this name already exists in scope and the OLD binding is an
        // import, record a redefinition (import overwritten by def/class/etc.).
        if let Some(&existing_id) = self.scopes[scope_id as usize].bindings.get(&name) {
            let old = &self.bindings[existing_id];
            if (old.flags & FLAG_IMPORT) != 0 {
                self.redefinitions.push(Redefinition {
                    name: name.clone(),
                    scope_id,
                    new_line: line,
                    new_column: column,
                    old_line: old.line,
                });
            }
        }

        self.bindings.push(BindingBuilder::new(
            name.clone(),
            node_id,
            start_byte,
            end_byte,
            line,
            column,
            scope_id,
            flags,
            valid_until_byte,
        ));

        self.scopes[scope_id as usize]
            .bindings
            .insert(name, binding_id);
        binding_id
    }

    fn add_binding_from_info(
        &mut self,
        info: NameInfo,
        flags: u8,
        valid_until_byte: Option<usize>,
        target_scope: Option<i64>,
    ) -> usize {
        self.add_binding(
            info.name,
            info.node_id,
            info.start_byte,
            info.end_byte,
            info.line,
            info.column,
            flags,
            valid_until_byte,
            target_scope,
        )
    }

    fn get_node_text(&self, node: Node) -> String {
        let text = &self.source[node.start_byte()..node.end_byte()];
        String::from_utf8_lossy(text).into_owned()
    }

    /// Bind parameters from a `parameters` or `lambda_parameters` node.
    fn bind_parameters(&mut self, node: Node) {
        let fk = self.fk;
        if let Some(params) = node.child_by_field_id(fk.parameters) {
            let param_infos: Vec<NameInfo> = {
                let mut cursor = params.walk();
                params
                    .named_children(&mut cursor)
                    .filter_map(|param| self.extract_param_info(param))
                    .collect()
            };
            for info in param_infos {
                self.add_binding_from_info(info, FLAG_PARAMETER, None, None);
            }
        }
    }

    /// Handle a `global_statement` or `nonlocal_statement`.
    fn handle_declaration(&mut self, node: Node, is_global: bool) {
        let nk = self.nk;
        let idents: Vec<(String, i64, usize, u32, u32)> = {
            let mut cursor = node.walk();
            node.named_children(&mut cursor)
                .filter(|child| child.kind_id() == nk.identifier)
                .map(|child| {
                    let name = self.get_node_text(child);
                    (
                        name,
                        child.id() as i64,
                        child.start_byte(),
                        node_line(child),
                        node_col(child),
                    )
                })
                .collect()
        };
        let scope_id = self.current_scope();
        for (name, cid, start_byte, line, col) in idents {
            if is_global {
                self.scopes[scope_id as usize].globals.insert(name.clone());
            } else {
                self.scopes[scope_id as usize]
                    .nonlocals
                    .insert(name.clone());
            }
            self.declarations.push(Declaration {
                name,
                node_id: cid,
                start_byte,
                line,
                column: col,
                scope_id,
                is_global,
            });
        }
    }

    /// Extract names from a target node and bind them if not already bound.
    /// When `track_for_loop` is true, also records for-loop bindings for F402.
    fn bind_target_names(&mut self, target: Node, track_for_loop: bool) {
        let name_infos: Vec<NameInfo> = {
            let mut result = Vec::new();
            self.extract_name_infos(target, &mut result);
            result
        };
        let scope_id = self.current_scope();
        for info in name_infos {
            if track_for_loop {
                self.for_loop_bindings
                    .push((info.name.clone(), info.line, info.column));
            }
            if !self.scopes[scope_id as usize]
                .bindings
                .contains_key(&info.name)
            {
                self.add_binding_from_info(info, 0, None, None);
            }
        }
    }

    /// Bind identifiers from an `as_pattern_target` inside an `as_pattern`.
    fn bind_as_pattern_target(&mut self, node: Node, flags: u8, valid_until: Option<usize>) {
        let nk = self.nk;
        if let Some(as_pattern) = find_first(node, nk.as_pattern)
            && let Some(target) = find_first(as_pattern, nk.as_pattern_target)
        {
            let ident_infos: Vec<NameInfo> = {
                let mut cursor = target.walk();
                target
                    .named_children(&mut cursor)
                    .filter(|child| child.kind_id() == nk.identifier)
                    .map(|child| NameInfo::from_node(child, self.source))
                    .collect()
            };
            for info in ident_infos {
                self.add_binding_from_info(info, flags, valid_until, None);
            }
        }
    }

    /// Resolve a binding, respecting exception handler bounds.
    fn resolve_binding(&self, name: &str, use_byte: usize) -> Option<usize> {
        let mut scope_id = self.current_scope();

        while scope_id != NO_SCOPE {
            let scope = &self.scopes[scope_id as usize];
            if let Some(&binding_id) = scope.bindings.get(name) {
                let binding = &self.bindings[binding_id];
                if let Some(valid_until) = binding.valid_until_byte
                    && use_byte >= valid_until
                {
                    scope_id = scope.parent;
                    continue;
                }
                return Some(binding_id);
            }
            scope_id = scope.parent;
        }

        None
    }

    /// Main analysis entry point.
    fn analyze(&mut self, root: Node) {
        self.push_scope(
            SCOPE_MODULE,
            root.id() as i64,
            root.start_byte(),
            root.end_byte(),
        );
        self.analyze_node(root, 0, 0);
        self.pop_scope();
    }

    /// Record context for "interesting" statement nodes.
    fn record_context(&mut self, node: Node) {
        self.context_map.insert(
            node.start_byte(),
            (self.context_flags, self.loop_depth, self.function_depth),
        );
    }

    /// Recursively analyze a node and build scope tree.
    fn analyze_node(&mut self, node: Node, parent_kind_id: u16, depth: u32) {
        if depth > MAX_ANALYZE_DEPTH {
            // Guard against adversarial deeply-nested input; see
            // tests/core/test_pathological_inputs.py for the regression.
            return;
        }
        let node_id = node.id() as i64;
        let kind_id = node.kind_id();

        // Copy ID registries to locals (avoids borrow conflicts with &mut self)
        let nk = self.nk;
        let fk = self.fk;

        self.node_count += 1;

        // Collect grouped node data during the same traversal
        let include = match self.group_filter {
            None => true,
            Some(set) => set.contains(&kind_id),
        };
        if include {
            let end_pos = node.end_position();
            let child_count = node.child_count() as u32;
            let first_child_kind_id = node.child(0).map_or(0, |c| c.kind_id());
            let last_child_kind_id = if child_count > 1 {
                node.child(child_count - 1).map_or(0, |c| c.kind_id())
            } else {
                first_child_kind_id
            };

            self.raw_groups
                .entry(kind_id)
                .or_default()
                .push(RawNodeEntry {
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

        // Collect string_lines for multi-line strings
        if kind_id == nk.string {
            let start_row = node.start_position().row as u32 + 1;
            let end_row = node.end_position().row as u32 + 1;
            if end_row > start_row {
                for ln in (start_row + 1)..=end_row {
                    self.string_lines.push(ln);
                }
            }
        }

        // Collect noqa directives from comments
        if kind_id == nk.comment {
            let text = &self.source[node.start_byte()..node.end_byte()];
            if let Some(noqa) = parse_noqa(text) {
                let line = node.start_position().row as u32 + 1;
                self.noqa_lines.insert(line, noqa);
            }
        }

        let mut creates_scope = false;

        // Save context state for restoration after children
        let saved_flags = self.context_flags;
        let saved_loop_depth = self.loop_depth;
        let saved_function_depth = self.function_depth;
        // Track whether we need to restore context
        let mut context_changed = false;

        match kind_id {
            k if k == nk.function_definition || k == nk.async_function_definition => {
                // Bind function name in current scope (before pushing new scope)
                if let Some(name_node) = node.child_by_field_id(fk.name) {
                    let info = NameInfo::from_node(name_node, self.source);
                    self.add_binding_from_info(info, 0, None, None);
                }

                self.push_scope(SCOPE_FUNCTION, node_id, node.start_byte(), node.end_byte());
                creates_scope = true;

                // Context: enter function, reset loop depth
                self.context_flags |= CTX_IN_FUNCTION;
                self.context_flags &= !CTX_IN_LOOP;
                self.function_depth += 1;
                self.loop_depth = 0;
                context_changed = true;

                self.bind_parameters(node);
            }

            k if k == nk.class_definition => {
                // Bind class name in current scope (before pushing new scope)
                if let Some(name_node) = node.child_by_field_id(fk.name) {
                    let info = NameInfo::from_node(name_node, self.source);
                    self.add_binding_from_info(info, 0, None, None);
                }

                self.push_scope(SCOPE_CLASS, node_id, node.start_byte(), node.end_byte());
                creates_scope = true;

                // Context: enter class
                self.context_flags |= CTX_IN_CLASS;
                context_changed = true;
            }

            k if k == nk.lambda => {
                self.push_scope(SCOPE_FUNCTION, node_id, node.start_byte(), node.end_byte());
                creates_scope = true;

                // Context: enter lambda, reset loop depth
                self.context_flags |= CTX_IN_LAMBDA | CTX_IN_FUNCTION;
                self.context_flags &= !CTX_IN_LOOP;
                self.function_depth += 1;
                self.loop_depth = 0;
                context_changed = true;

                self.bind_parameters(node);
            }

            k if k == nk.list_comprehension
                || k == nk.set_comprehension
                || k == nk.dictionary_comprehension
                || k == nk.generator_expression =>
            {
                self.push_scope(
                    SCOPE_COMPREHENSION,
                    node_id,
                    node.start_byte(),
                    node.end_byte(),
                );
                creates_scope = true;

                // Context: enter comprehension
                self.context_flags |= CTX_IN_COMPREHENSION;
                context_changed = true;

                // Pre-bind iteration variables before processing the expression
                {
                    let lefts: Vec<Node> = {
                        let mut cursor = node.walk();
                        node.children(&mut cursor)
                            .filter(|c| c.kind_id() == nk.for_in_clause)
                            .filter_map(|c| c.child_by_field_id(fk.left))
                            .collect()
                    };
                    for left in lefts {
                        self.bind_target_names(left, false);
                    }
                }
            }

            k if k == nk.assignment => {
                // Check for annotation-only: x: int (has type but no right/value)
                let type_node = node.child_by_field_id(fk.type_);
                let right_node = node.child_by_field_id(fk.right);

                if type_node.is_some()
                    && right_node.is_none()
                    && let Some(left_node) = node.child_by_field_id(fk.left)
                    && left_node.kind_id() == nk.identifier
                {
                    let name = self.get_node_text(left_node);
                    let scope_id = self.current_scope();
                    self.annotation_only.push(AnnotationRef {
                        name,
                        node_id: left_node.id() as i64,
                        start_byte: left_node.start_byte(),
                        line: node_line(left_node),
                        column: node_col(left_node),
                        scope_id,
                    });
                }
                self.handle_assignment(node);
            }

            k if k == nk.augmented_assignment => {
                self.handle_assignment(node);
            }

            k if k == nk.import_statement
                || k == nk.import_from_statement
                || k == nk.future_import_statement =>
            {
                self.handle_import(node);
            }

            k if k == nk.for_statement || k == nk.async_for_statement => {
                if let Some(left) = node.child_by_field_id(fk.left) {
                    self.bind_target_names(left, true);
                }

                // Context: enter loop
                self.context_flags |= CTX_IN_LOOP;
                self.loop_depth += 1;
                context_changed = true;
            }

            k if k == nk.while_statement => {
                // Context: enter loop
                self.context_flags |= CTX_IN_LOOP;
                self.loop_depth += 1;
                context_changed = true;
            }

            k if k == nk.try_statement => {
                self.context_flags |= CTX_IN_TRY;
                context_changed = true;
            }

            k if k == nk.for_in_clause => {
                if let Some(left) = node.child_by_field_id(fk.left) {
                    self.bind_target_names(left, false);
                }
            }

            k if k == nk.named_expression => {
                if let Some(name_node) = node.child_by_field_id(fk.name)
                    && name_node.kind_id() == nk.identifier
                {
                    // Walrus operator: bind in enclosing non-comprehension scope
                    let mut target_scope = self.current_scope();
                    while self.scopes[target_scope as usize].type_ == SCOPE_COMPREHENSION
                        && self.scopes[target_scope as usize].parent != NO_SCOPE
                    {
                        target_scope = self.scopes[target_scope as usize].parent;
                    }

                    let info = NameInfo::from_node(name_node, self.source);
                    self.add_binding_from_info(info, 0, None, Some(target_scope));
                }
            }

            k if k == nk.global_statement => {
                self.handle_declaration(node, true);
            }

            k if k == nk.nonlocal_statement => {
                self.handle_declaration(node, false);
            }

            k if k == nk.except_clause => {
                // Context: enter except
                self.context_flags |= CTX_IN_EXCEPT;
                context_changed = true;

                self.bind_as_pattern_target(node, FLAG_EXCEPTION, Some(node.end_byte()));
            }

            k if k == nk.with_item => {
                self.bind_as_pattern_target(node, 0, None);
            }

            k if k == nk.case_clause => {
                let case_patterns: Vec<Node> = find_all(node, nk.case_pattern);
                for pattern in case_patterns {
                    let dotted_names: Vec<Node> = find_all(pattern, nk.dotted_name);
                    for dotted in dotted_names {
                        let mut cursor = dotted.walk();
                        let children: Vec<_> = dotted.named_children(&mut cursor).collect();
                        if children.len() == 1 && children[0].kind_id() == nk.identifier {
                            let info = NameInfo::from_node(children[0], self.source);
                            self.add_binding_from_info(info, 0, None, None);
                        }
                    }
                }
            }

            k if k == nk.with_statement || k == nk.async_with_statement => {
                self.context_flags |= CTX_IN_WITH;
                context_changed = true;
            }

            k if k == nk.finally_clause => {
                self.context_flags |= CTX_IN_FINALLY;
                context_changed = true;
            }

            // Record context for interesting statement nodes
            k if k == nk.break_statement
                || k == nk.continue_statement
                || k == nk.return_statement
                || k == nk.yield_expr
                || k == nk.yield_statement =>
            {
                self.record_context(node);
            }

            k if k == nk.identifier && !self.is_binding_context(node) => {
                let scope_id = self.current_scope();
                let name = self.get_node_text(node);
                let start_byte = node.start_byte();
                let line = node_line(node);
                let col = node_col(node);

                // Record use with line/col for F823 (avoids tree search)
                self.scopes[scope_id as usize].uses.push(NameUse {
                    name: name.clone(),
                    node_id,
                    start_byte,
                    line,
                    column: col,
                });

                if let Some(binding_id) = self.resolve_binding(&name, start_byte) {
                    self.bindings[binding_id].references.push(node_id);
                } else {
                    // Track unresolved names for F821
                    self.unresolved.push(UnresolvedRef {
                        name,
                        node_id,
                        start_byte,
                        line,
                        column: col,
                        scope_id,
                    });
                }
            }

            _ => {}
        }

        // Recurse into children
        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            self.analyze_node(child, kind_id, depth + 1);
        }

        if creates_scope {
            self.pop_scope();
        }

        // Restore context state
        if context_changed {
            self.context_flags = saved_flags;
            self.loop_depth = saved_loop_depth;
            self.function_depth = saved_function_depth;
        }
    }

    fn extract_param_info(&self, param: Node) -> Option<NameInfo> {
        let pk = param.kind_id();
        if pk == self.nk.identifier {
            Some(NameInfo::from_node(param, self.source))
        } else if pk == self.nk.typed_parameter
            || pk == self.nk.default_parameter
            || pk == self.nk.typed_default_parameter
        {
            if let Some(name) = param.child_by_field_id(self.fk.name) {
                return Some(NameInfo::from_node(name, self.source));
            }
            let mut cursor = param.walk();
            for child in param.named_children(&mut cursor) {
                if child.kind_id() == self.nk.identifier {
                    return Some(NameInfo::from_node(child, self.source));
                }
                // Handle typed splat params: **kwargs: T / *args: T
                // where the identifier is nested inside a splat pattern
                if child.kind_id() == self.nk.list_splat_pattern
                    || child.kind_id() == self.nk.dictionary_splat_pattern
                {
                    let mut sc = child.walk();
                    for grandchild in child.named_children(&mut sc) {
                        if grandchild.kind_id() == self.nk.identifier {
                            return Some(NameInfo::from_node(grandchild, self.source));
                        }
                    }
                }
            }
            None
        } else if pk == self.nk.list_splat_pattern || pk == self.nk.dictionary_splat_pattern {
            let mut cursor = param.walk();
            for child in param.named_children(&mut cursor) {
                if child.kind_id() == self.nk.identifier {
                    return Some(NameInfo::from_node(child, self.source));
                }
            }
            None
        } else {
            None
        }
    }

    fn extract_name_infos(&self, node: Node, result: &mut Vec<NameInfo>) {
        let nk_id = node.kind_id();
        if nk_id == self.nk.identifier {
            result.push(NameInfo::from_node(node, self.source));
        } else if nk_id == self.nk.tuple
            || nk_id == self.nk.list
            || nk_id == self.nk.tuple_pattern
            || nk_id == self.nk.list_pattern
            || nk_id == self.nk.pattern_list
        {
            let mut cursor = node.walk();
            for child in node.named_children(&mut cursor) {
                self.extract_name_infos(child, result);
            }
        } else if nk_id == self.nk.list_splat_pattern || nk_id == self.nk.dictionary_splat_pattern {
            let mut cursor = node.walk();
            for child in node.named_children(&mut cursor) {
                if child.kind_id() == self.nk.identifier {
                    result.push(NameInfo::from_node(child, self.source));
                }
            }
        }
    }

    fn handle_assignment(&mut self, node: Node) {
        let fk = self.fk;
        let nk = self.nk;
        let Some(left) = node.child_by_field_id(fk.left) else {
            return;
        };

        // Detect module-level `__all__ = [...]` or `__all__ = (...)`
        let scope_id = self.current_scope();
        if scope_id == 0
            && left.kind_id() == nk.identifier
            && self.get_node_text(left) == "__all__"
            && let Some(right) = node.child_by_field_id(fk.right)
        {
            self.extract_dunder_all(right);
        }

        // Collect name info before mutating
        let name_infos: Vec<NameInfo> = {
            let mut result = Vec::new();
            self.extract_name_infos(left, &mut result);
            result
        };
        for info in name_infos {
            // Check if binding already exists (redefinition)
            if let Some(&existing_id) = self.scopes[scope_id as usize].bindings.get(&info.name) {
                // F811: only record redefinition when the OLD binding is an import.
                // Variable-to-variable reassignment (x = 1; x = 2) is normal Python
                // and should NOT be flagged.
                let old = &self.bindings[existing_id];
                if (old.flags & FLAG_IMPORT) != 0 {
                    self.redefinitions.push(Redefinition {
                        name: info.name.clone(),
                        scope_id,
                        new_line: info.line,
                        new_column: info.column,
                        old_line: old.line,
                    });
                }
                continue;
            }

            let mut flags = 0u8;
            if self.scopes[scope_id as usize].globals.contains(&info.name) {
                flags = FLAG_GLOBAL;
            } else if self.scopes[scope_id as usize]
                .nonlocals
                .contains(&info.name)
            {
                flags = FLAG_NONLOCAL;
            }

            self.add_binding_from_info(info, flags, None, None);
        }
    }

    /// Extract names from a `__all__` list/tuple literal (or `__all__ += [...]`).
    fn extract_dunder_all(&mut self, node: Node) {
        let nk = self.nk;
        let kind = node.kind_id();
        if kind == nk.list || kind == nk.tuple {
            let mut cursor = node.walk();
            for child in node.named_children(&mut cursor) {
                if child.kind_id() == nk.string {
                    let text = self.get_node_text(child);
                    // Strip quotes: "name" / 'name' / """name""" / '''name'''
                    let s = text.trim_start_matches(['"', '\'']);
                    let s = s.trim_end_matches(['"', '\'']);
                    if !s.is_empty() {
                        self.dunder_all_names.insert(s.to_string());
                    }
                }
            }
        }
    }

    #[allow(clippy::type_complexity)]
    fn handle_import(&mut self, node: Node) {
        let nk = self.nk;
        let fk = self.fk;
        let scope_id = self.current_scope();
        let stmt_line = node_line(node);
        let stmt_col = node_col(node);
        let node_kind = node.kind_id();

        if node_kind == nk.import_statement {
            // Collect import info before mutating
            // Each entry: (bound_name, full_module, original_name, is_aliased, node_id, start, end, line, col)
            let imports: Vec<(String, String, String, bool, i64, usize, usize, u32, u32)> = {
                let mut cursor = node.walk();
                let mut result = Vec::new();
                for child in node.named_children(&mut cursor) {
                    let ck = child.kind_id();
                    if ck == nk.dotted_name {
                        let text = self.get_node_text(child);
                        let parts: Vec<&str> = text.split('.').collect();
                        result.push((
                            parts[0].to_string(),
                            text.clone(),
                            text,
                            false,
                            child.id() as i64,
                            child.start_byte(),
                            child.end_byte(),
                            node_line(child),
                            node_col(child),
                        ));
                    } else if ck == nk.aliased_import {
                        let alias = child.child_by_field_id(fk.alias);
                        let name = child.child_by_field_id(fk.name);

                        if let (Some(alias_node), Some(name_node)) = (alias, name) {
                            let bound_name = self.get_node_text(alias_node);
                            let module = self.get_node_text(name_node);
                            result.push((
                                bound_name,
                                module.clone(),
                                module,
                                true,
                                child.id() as i64,
                                alias_node.start_byte(),
                                alias_node.end_byte(),
                                node_line(alias_node),
                                node_col(alias_node),
                            ));
                        } else if let Some(name_node) = name {
                            let text = self.get_node_text(name_node);
                            let parts: Vec<&str> = text.split('.').collect();
                            result.push((
                                parts[0].to_string(),
                                text.clone(),
                                text,
                                false,
                                child.id() as i64,
                                name_node.start_byte(),
                                name_node.end_byte(),
                                node_line(name_node),
                                node_col(name_node),
                            ));
                        }
                    }
                }
                result
            };

            for (bound_name, module, original_name, is_aliased, nid, start, end, line, col) in
                imports
            {
                let binding_id = self.add_binding(
                    bound_name,
                    nid,
                    start,
                    end,
                    line,
                    col,
                    FLAG_IMPORT,
                    None,
                    None,
                );
                let info_idx = self.import_infos.len();
                self.import_infos.push(ImportInfo::new(
                    binding_id as i64,
                    module,
                    original_name,
                    false,
                    is_aliased,
                    false,
                    false,
                    false,
                    scope_id,
                    stmt_line,
                    stmt_col,
                ));
                self.binding_import_map.insert(binding_id, info_idx);
            }
        } else {
            // import_from_statement or future_import_statement
            let is_future = node_kind == nk.future_import_statement;

            // Extract module name and relative-ness first
            let (module_name, is_relative) = {
                if is_future {
                    // future_import_statement: __future__ is a keyword, not a dotted_name
                    ("__future__".to_string(), false)
                } else {
                    let mut module = String::new();
                    let mut relative = false;
                    let mut cursor = node.walk();
                    for child in node.children(&mut cursor) {
                        if !child.is_named() {
                            continue;
                        }
                        let ck = child.kind_id();
                        if ck == nk.relative_import {
                            relative = true;
                            let mut inner_cursor = child.walk();
                            for inner in child.named_children(&mut inner_cursor) {
                                if inner.kind_id() == nk.dotted_name {
                                    module = self.get_node_text(inner);
                                }
                            }
                            break;
                        } else if ck == nk.dotted_name {
                            module = self.get_node_text(child);
                            break;
                        }
                    }
                    (module, relative)
                }
            };

            // Collect imported names
            // (bound_name, original_name, is_aliased, is_star, node_id, start, end, line, col)
            let imports: Vec<(String, String, bool, bool, i64, usize, usize, u32, u32)> = {
                // For future_import_statement, __future__ is a keyword (not named),
                // so there's no dotted_name for the module - start with module_found=true
                let mut module_found = is_future;
                let mut cursor = node.walk();
                let mut result = Vec::new();

                for child in node.children(&mut cursor) {
                    if !child.is_named() {
                        continue;
                    }

                    let ck = child.kind_id();
                    if ck == nk.relative_import {
                        module_found = true;
                    } else if ck == nk.dotted_name {
                        if !module_found {
                            module_found = true;
                        } else {
                            let text = self.get_node_text(child);
                            result.push((
                                text.clone(),
                                text,
                                false,
                                false,
                                child.id() as i64,
                                child.start_byte(),
                                child.end_byte(),
                                node_line(child),
                                node_col(child),
                            ));
                        }
                    } else if ck == nk.aliased_import {
                        let alias = child.child_by_field_id(fk.alias);
                        let name = child.child_by_field_id(fk.name);

                        if let Some(alias_node) = alias {
                            let bound_name = self.get_node_text(alias_node);
                            let original = name.map(|n| self.get_node_text(n)).unwrap_or_default();
                            result.push((
                                bound_name,
                                original,
                                true,
                                false,
                                child.id() as i64,
                                alias_node.start_byte(),
                                alias_node.end_byte(),
                                node_line(alias_node),
                                node_col(alias_node),
                            ));
                        } else if let Some(name_node) = name {
                            let bound_name = self.get_node_text(name_node);
                            result.push((
                                bound_name.clone(),
                                bound_name,
                                false,
                                false,
                                child.id() as i64,
                                name_node.start_byte(),
                                name_node.end_byte(),
                                node_line(name_node),
                                node_col(name_node),
                            ));
                        }
                    } else if ck == nk.wildcard_import {
                        // Star import: no binding, but record ImportInfo
                        result.push((
                            "*".to_string(),
                            "*".to_string(),
                            false,
                            true,
                            child.id() as i64,
                            child.start_byte(),
                            child.end_byte(),
                            node_line(child),
                            node_col(child),
                        ));
                    }
                }
                result
            };

            for (bound_name, original_name, is_aliased, is_star, nid, start, end, line, col) in
                imports
            {
                let binding_id = if is_star {
                    -1i64 // Star imports don't create a named binding
                } else {
                    self.add_binding(
                        bound_name,
                        nid,
                        start,
                        end,
                        line,
                        col,
                        FLAG_IMPORT,
                        None,
                        None,
                    ) as i64
                };

                let info_idx = self.import_infos.len();
                self.import_infos.push(ImportInfo::new(
                    binding_id,
                    module_name.clone(),
                    original_name,
                    is_star,
                    is_aliased,
                    is_future || module_name == "__future__",
                    is_relative,
                    true,
                    scope_id,
                    stmt_line,
                    stmt_col,
                ));
                if binding_id >= 0 {
                    self.binding_import_map
                        .insert(binding_id as usize, info_idx);
                }
            }
        }
    }

    fn is_binding_context(&self, node: Node) -> bool {
        let Some(parent) = node.parent() else {
            return false;
        };

        let parent_kind = parent.kind_id();

        // Attribute access: obj.attr - 'attr' is NOT a name reference
        if parent_kind == self.nk.attribute
            && let Some(attr) = parent.child_by_field_id(self.fk.attribute)
            && attr.id() == node.id()
        {
            return true;
        }

        if (parent_kind == self.nk.assignment || parent_kind == self.nk.augmented_assignment)
            && let Some(left) = parent.child_by_field_id(self.fk.left)
            && contains_node(left, node)
        {
            return true;
        }

        if (parent_kind == self.nk.function_definition
            || parent_kind == self.nk.async_function_definition
            || parent_kind == self.nk.class_definition)
            && let Some(name) = parent.child_by_field_id(self.fk.name)
            && name.id() == node.id()
        {
            return true;
        }

        if parent_kind == self.nk.parameters
            || parent_kind == self.nk.lambda_parameters
            || parent_kind == self.nk.typed_parameter
            || parent_kind == self.nk.default_parameter
            || parent_kind == self.nk.typed_default_parameter
            || parent_kind == self.nk.list_splat_pattern
            || parent_kind == self.nk.dictionary_splat_pattern
        {
            return true;
        }

        // Keyword argument name (e.g., 'key' in func(key=value))
        if parent_kind == self.nk.keyword_argument
            && let Some(name) = parent.child_by_field_id(self.fk.name)
            && name.id() == node.id()
        {
            return true;
        }

        if (parent_kind == self.nk.for_statement
            || parent_kind == self.nk.async_for_statement
            || parent_kind == self.nk.for_in_clause)
            && let Some(left) = parent.child_by_field_id(self.fk.left)
            && contains_node(left, node)
        {
            return true;
        }

        if parent_kind == self.nk.named_expression
            && let Some(name) = parent.child_by_field_id(self.fk.name)
            && name.id() == node.id()
        {
            return true;
        }

        if parent_kind == self.nk.dotted_name || parent_kind == self.nk.aliased_import {
            if let Some(gp) = parent.parent() {
                let gp_kind = gp.kind_id();
                if gp_kind == self.nk.import_statement
                    || gp_kind == self.nk.import_from_statement
                    || gp_kind == self.nk.future_import_statement
                {
                    return true;
                }
                if gp_kind == self.nk.relative_import {
                    return true;
                }
                if gp_kind == self.nk.aliased_import {
                    return true;
                }
            }
            if parent_kind == self.nk.aliased_import
                && let Some(alias) = parent.child_by_field_id(self.fk.alias)
                && alias.id() == node.id()
            {
                return true;
            }
        }

        if parent_kind == self.nk.global_statement || parent_kind == self.nk.nonlocal_statement {
            return true;
        }

        if (parent_kind == self.nk.tuple
            || parent_kind == self.nk.list
            || parent_kind == self.nk.tuple_pattern
            || parent_kind == self.nk.list_pattern
            || parent_kind == self.nk.pattern_list)
            && let Some(gp) = parent.parent()
        {
            let gp_kind = gp.kind_id();
            if (gp_kind == self.nk.assignment || gp_kind == self.nk.augmented_assignment)
                && let Some(left) = gp.child_by_field_id(self.fk.left)
                && contains_node(left, node)
            {
                return true;
            }
            return self.is_binding_context(parent);
        }

        // except_clause: the exception TYPE (e.g., FooError in `except FooError:`)
        // is a reference, NOT a binding. The `as` target is already handled by
        // bind_as_pattern_target, so we do NOT mark except_clause children as binding.

        if (parent_kind == self.nk.with_clause || parent_kind == self.nk.with_item)
            && let Some(gp) = parent.parent()
            && gp.kind_id() == self.nk.with_statement
        {
            return true;
        }

        false
    }

    /// Extract owned analysis data — pure Rust, no GIL needed.
    fn into_result(self) -> AnalysisResult {
        let string_lines_set: FxHashSet<u32> = self.string_lines.iter().copied().collect();
        let line_infos = compute_line_infos(self.source, &string_lines_set);
        AnalysisResult {
            lang: self.lang,
            scopes: self.scopes,
            bindings: self.bindings,
            unresolved: self.unresolved,
            annotation_only: self.annotation_only,
            declarations: self.declarations,
            redefinitions: self.redefinitions,
            node_count: self.node_count,
            for_loop_bindings: self.for_loop_bindings,
            context_map: self.context_map,
            import_infos: self.import_infos,
            binding_import_map: self.binding_import_map,
            dunder_all_names: self.dunder_all_names,
            string_lines: self.string_lines,
            noqa_lines: self.noqa_lines,
            raw_groups: Some(self.raw_groups),
            line_infos,
        }
    }
}

impl AnalysisResult {
    /// Take the raw_groups out, leaving None in place.
    pub(crate) fn take_groups(&mut self) -> RawGroups {
        self.raw_groups.take().unwrap_or_default()
    }

    /// Convert the owned analysis result into a SemanticModel (needs GIL).
    pub(crate) fn into_model(self, py: Python<'_>) -> PyResult<SemanticModel> {
        let lang = self.lang;

        // Pre-compute unused variables (F841) and unused imports (F401)
        let mut unused_variables: Vec<UnusedBinding> = Vec::new();
        let mut unused_imports: Vec<UnusedBinding> = Vec::new();

        for (binding_idx, b) in self.bindings.iter().enumerate() {
            let is_used = !b.references.is_empty();

            if is_used || b.name.starts_with('_') {
                continue;
            }

            let is_import = (b.flags & FLAG_IMPORT) != 0;
            let is_parameter = (b.flags & FLAG_PARAMETER) != 0;
            let is_global = (b.flags & FLAG_GLOBAL) != 0;
            let is_nonlocal = (b.flags & FLAG_NONLOCAL) != 0;

            if is_import {
                // Skip __future__ imports — they are directives, not real imports
                if let Some(&info_idx) = self.binding_import_map.get(&binding_idx)
                    && self.import_infos[info_idx].is_future
                {
                    continue;
                }
                if b.scope == 0 && !self.dunder_all_names.contains(&b.name) {
                    unused_imports.push(UnusedBinding {
                        name: b.name.clone(),
                        line: b.line,
                        column: b.column,
                        start_byte: b.start_byte,
                        end_byte: b.end_byte,
                        scope_id: NO_SCOPE,
                    });
                }
            } else if !is_parameter && !is_global && !is_nonlocal {
                let scope = &self.scopes[b.scope as usize];
                if scope.type_ == SCOPE_FUNCTION {
                    unused_variables.push(UnusedBinding {
                        name: b.name.clone(),
                        line: b.line,
                        column: b.column,
                        start_byte: b.start_byte,
                        end_byte: b.end_byte,
                        scope_id: b.scope,
                    });
                }
            }
        }

        // Pre-compute unused annotations (F842)
        let mut unused_annotations: Vec<UnusedName> = Vec::new();
        for ann in &self.annotation_only {
            let scope = &self.scopes[ann.scope_id as usize];
            if scope.type_ != SCOPE_FUNCTION {
                continue;
            }
            let is_used = if let Some(&binding_id) = scope.bindings.get(&ann.name) {
                !self.bindings[binding_id].references.is_empty()
            } else {
                scope.uses.iter().any(|u| u.name == ann.name)
            };
            if !is_used {
                unused_annotations.push(UnusedName {
                    name: ann.name.clone(),
                    line: ann.line,
                    column: ann.column,
                });
            }
        }

        // Pre-compute unused declarations (F824)
        let mut unused_declarations: Vec<UnusedDeclaration> = Vec::new();
        for decl in &self.declarations {
            let scope = &self.scopes[decl.scope_id as usize];
            if !scope.bindings.contains_key(&decl.name) {
                unused_declarations.push(UnusedDeclaration {
                    name: decl.name.clone(),
                    line: decl.line,
                    column: decl.column,
                    is_global: decl.is_global,
                });
            }
        }

        // Pre-compute undefined locals (F823)
        let mut undefined_locals: Vec<UnusedName> = Vec::new();
        for scope in &self.scopes {
            if scope.type_ != SCOPE_FUNCTION {
                continue;
            }
            let mut binding_positions: FxHashMap<&str, usize> = FxHashMap::default();
            let mut exception_names: FxHashSet<&str> = FxHashSet::default();
            for (name, &binding_id) in &scope.bindings {
                let binding = &self.bindings[binding_id];
                let is_parameter = (binding.flags & FLAG_PARAMETER) != 0;
                let is_exception = (binding.flags & FLAG_EXCEPTION) != 0;
                if is_parameter {
                    binding_positions.insert(name, 0);
                } else {
                    binding_positions.insert(name, binding.start_byte);
                    if is_exception {
                        exception_names.insert(name);
                    }
                }
            }
            for u in &scope.uses {
                if let Some(&binding_pos) = binding_positions.get(u.name.as_str())
                    && u.start_byte < binding_pos
                {
                    if scope.globals.contains(&u.name) || scope.nonlocals.contains(&u.name) {
                        continue;
                    }
                    if exception_names.contains(u.name.as_str()) {
                        continue;
                    }
                    undefined_locals.push(UnusedName {
                        name: u.name.clone(),
                        line: u.line,
                        column: u.column,
                    });
                }
            }
        }

        // Pre-compute shadowed imports (F402)
        let mut shadowed_imports: Vec<ShadowedImport> = Vec::new();
        if !self.scopes.is_empty() {
            let mut module_imports: FxHashMap<&str, u32> = FxHashMap::default();
            for b in &self.bindings {
                if (b.flags & FLAG_IMPORT) != 0 && b.scope == 0 {
                    module_imports.entry(&b.name).or_insert(b.line);
                }
            }
            for (name, loop_line, loop_col) in &self.for_loop_bindings {
                if let Some(&import_line) = module_imports.get(name.as_str())
                    && *loop_line > import_line
                {
                    shadowed_imports.push(ShadowedImport {
                        name: name.clone(),
                        loop_line: *loop_line,
                        loop_column: *loop_col,
                        import_line,
                    });
                }
            }
        }

        // Convert bindings
        let bindings: Vec<Py<Binding>> = self
            .bindings
            .into_iter()
            .map(|b| {
                Py::new(
                    py,
                    Binding::with_references(
                        b.name,
                        b.node_id,
                        b.start_byte,
                        b.end_byte,
                        b.line,
                        b.column,
                        b.scope,
                        b.flags,
                        b.valid_until_byte,
                        b.references,
                    ),
                )
            })
            .collect::<PyResult<Vec<_>>>()?;

        // Build node_id → scope_index map
        let node_id_to_scope: FxHashMap<i64, usize> = self
            .scopes
            .iter()
            .enumerate()
            .map(|(i, s)| (s.node_id, i))
            .collect();

        // Build sorted scope intervals for O(log n) scope_for_position
        let mut scope_intervals: Vec<(usize, usize, usize)> = self
            .scopes
            .iter()
            .enumerate()
            .map(|(i, s)| (s.start_byte, s.end_byte, i))
            .collect();
        scope_intervals.sort_by_key(|&(start, _, _)| start);

        // Convert scopes
        let scopes: Vec<Py<Scope>> = self
            .scopes
            .into_iter()
            .map(|s| {
                let uses = s
                    .uses
                    .into_iter()
                    .map(|u| (u.name, u.node_id, u.start_byte, u.line, u.column))
                    .collect();
                Py::new(
                    py,
                    Scope::with_data(
                        s.type_,
                        s.node_id,
                        s.parent,
                        s.start_byte,
                        s.end_byte,
                        s.bindings,
                        s.globals,
                        s.nonlocals,
                        s.children,
                        uses,
                    ),
                )
            })
            .collect::<PyResult<Vec<_>>>()?;

        // Convert import infos
        let import_infos: Vec<Py<ImportInfo>> = self
            .import_infos
            .into_iter()
            .map(|i| Py::new(py, i))
            .collect::<PyResult<Vec<_>>>()?;

        // Deduplicate and sort string_lines
        let mut string_lines = self.string_lines;
        string_lines.sort_unstable();
        string_lines.dedup();

        Ok(SemanticModel {
            scopes_vec: scopes,
            bindings_vec: bindings,
            lang,
            unresolved_vec: self
                .unresolved
                .into_iter()
                .map(|r| Py::new(py, r))
                .collect::<PyResult<Vec<_>>>()?,
            annotation_only_vec: self
                .annotation_only
                .into_iter()
                .map(|a| Py::new(py, a))
                .collect::<PyResult<Vec<_>>>()?,
            declarations_vec: self
                .declarations
                .into_iter()
                .map(|d| Py::new(py, d))
                .collect::<PyResult<Vec<_>>>()?,
            redefinitions_vec: self
                .redefinitions
                .into_iter()
                .map(|r| Py::new(py, r))
                .collect::<PyResult<Vec<_>>>()?,
            node_count: self.node_count,
            unused_variables_vec: unused_variables
                .into_iter()
                .map(|v| Py::new(py, v))
                .collect::<PyResult<Vec<_>>>()?,
            unused_imports_vec: unused_imports
                .into_iter()
                .map(|v| Py::new(py, v))
                .collect::<PyResult<Vec<_>>>()?,
            unused_annotations_vec: unused_annotations
                .into_iter()
                .map(|v| Py::new(py, v))
                .collect::<PyResult<Vec<_>>>()?,
            unused_declarations_vec: unused_declarations
                .into_iter()
                .map(|v| Py::new(py, v))
                .collect::<PyResult<Vec<_>>>()?,
            undefined_locals_vec: undefined_locals
                .into_iter()
                .map(|v| Py::new(py, v))
                .collect::<PyResult<Vec<_>>>()?,
            shadowed_imports_vec: shadowed_imports
                .into_iter()
                .map(|v| Py::new(py, v))
                .collect::<PyResult<Vec<_>>>()?,
            context_map: self.context_map,
            import_infos_vec: import_infos,
            binding_import_map: self.binding_import_map,
            node_id_to_scope,
            string_lines_vec: string_lines,
            noqa_lines_map: self.noqa_lines,
            line_infos_vec: self
                .line_infos
                .into_iter()
                .map(|t| {
                    Py::new(
                        py,
                        LineInfo {
                            leading_spaces: t.leading_spaces,
                            indent_len: t.indent_len,
                            line_len: t.line_len,
                            trailing_ws: t.trailing_ws,
                            comment_start: t.comment_start,
                            indent_has_tab: t.indent_has_tab,
                            indent_has_space: t.indent_has_space,
                            is_blank: t.is_blank,
                            is_in_string: t.is_in_string,
                            spaces_before_comment: t.spaces_before_comment,
                            char_after_hash: t.char_after_hash,
                            leading_hashes: t.leading_hashes,
                            style_flags: t.style_flags,
                        },
                    )
                })
                .collect::<PyResult<Vec<_>>>()?,
            scope_intervals,
        })
    }
}

/// Parse a `# noqa` directive from a comment's text bytes.
///
/// Returns:
/// - `None` — not a noqa comment
/// - `Some(None)` — blanket noqa (`# noqa`)
/// - `Some(Some(codes))` — specific noqa (`# noqa: E501,E302`)
fn parse_noqa(text: &[u8]) -> Option<Option<Vec<String>>> {
    let s = std::str::from_utf8(text).ok()?;
    // Find "noqa" case-insensitively
    let lower = s.to_ascii_lowercase();
    let idx = lower.find("noqa")?;
    let after = &s[idx + 4..];
    let after = after.trim_start();
    if after.is_empty() || !after.starts_with(':') {
        return Some(None); // blanket noqa
    }
    // Parse codes after ":"
    let codes_str = after[1..].trim();
    if codes_str.is_empty() {
        return Some(None);
    }
    let codes: Vec<String> = codes_str
        .split(',')
        .map(|c| c.trim().to_uppercase())
        .filter(|c| !c.is_empty())
        .collect();
    if codes.is_empty() {
        Some(None)
    } else {
        Some(Some(codes))
    }
}

///// Core analysis logic: produce AnalysisResult without GIL.
pub fn do_analyze_result(
    source: &[u8],
    root: Node,
    group_filter: &Option<FxHashSet<u16>>,
) -> AnalysisResult {
    let lang: Language = tree_sitter_python::LANGUAGE.into();
    let mut analyzer = Analyzer::new(source, lang, group_filter);
    analyzer.analyze(root);
    analyzer.into_result()
}

/// Parse and analyze Python source, returning a complete SemanticModel.
///
/// Accepts either raw `source` bytes (parses internally) or a pre-parsed
/// `TSTree` (reuses the tree, avoiding double parsing).
#[pyfunction]
#[pyo3(signature = (source=None, *, tree=None))]
pub fn analyze_source(
    py: Python<'_>,
    source: Option<&[u8]>,
    tree: Option<&TSTree>,
) -> PyResult<SemanticModel> {
    match (source, tree) {
        (_, Some(ts_tree)) => {
            // Release the GIL for the pure-Rust analysis phase.
            // Arc<TreeData> is Send+Sync so it can be used without the GIL.
            let data = ts_tree.data.clone();
            let result = py.detach(|| {
                let root = data.tree.root_node();
                do_analyze_result(data.source_bytes(), root, &None)
            });
            result.into_model(py)
        }
        (Some(src), None) => {
            // Copy bytes so we can release the GIL for parsing + analysis.
            let src_owned = src.to_vec();
            let result = py
                .detach(|| -> Result<AnalysisResult, String> {
                    let mut parser = Parser::new();
                    parser
                        .set_language(&tree_sitter_python::LANGUAGE.into())
                        .map_err(|e| format!("Failed to set language: {e}"))?;
                    let parsed = parser
                        .parse(&src_owned, None)
                        .ok_or_else(|| "Failed to parse source".to_string())?;
                    Ok(do_analyze_result(&src_owned, parsed.root_node(), &None))
                })
                .map_err(pyo3::exceptions::PyRuntimeError::new_err)?;
            result.into_model(py)
        }
        (None, None) => Err(pyo3::exceptions::PyValueError::new_err(
            "Either 'source' or 'tree' must be provided",
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ─────────────────────────────────────────────────────────────────────
    // parse_noqa
    // ─────────────────────────────────────────────────────────────────────

    #[test]
    fn test_parse_noqa_bare() {
        // "# noqa" -> Some(None) meaning blanket noqa
        let result = parse_noqa(b"# noqa");
        assert_eq!(result, Some(None));
    }

    #[test]
    fn test_parse_noqa_bare_trailing_space() {
        let result = parse_noqa(b"# noqa   ");
        assert_eq!(result, Some(None));
    }

    #[test]
    fn test_parse_noqa_with_single_code() {
        // "# noqa: E711" -> Some(Some(["E711"]))
        let result = parse_noqa(b"# noqa: E711");
        assert_eq!(result, Some(Some(vec!["E711".to_string()])));
    }

    #[test]
    fn test_parse_noqa_with_multiple_codes() {
        let result = parse_noqa(b"# noqa: E711,F401");
        assert_eq!(
            result,
            Some(Some(vec!["E711".to_string(), "F401".to_string()]))
        );
    }

    #[test]
    fn test_parse_noqa_with_spaces_between_codes() {
        let result = parse_noqa(b"# noqa: E711, F401, W292");
        assert_eq!(
            result,
            Some(Some(vec![
                "E711".to_string(),
                "F401".to_string(),
                "W292".to_string(),
            ]))
        );
    }

    #[test]
    fn test_parse_noqa_case_insensitive() {
        assert_eq!(parse_noqa(b"# NOQA"), Some(None));
        assert_eq!(parse_noqa(b"# Noqa"), Some(None));
        assert_eq!(
            parse_noqa(b"# NOQA: e711"),
            Some(Some(vec!["E711".to_string()]))
        );
    }

    #[test]
    fn test_parse_noqa_no_comment() {
        // Plain code line with no noqa directive
        assert_eq!(parse_noqa(b"x = 1"), None);
    }

    #[test]
    fn test_parse_noqa_empty_input() {
        assert_eq!(parse_noqa(b""), None);
    }

    #[test]
    fn test_parse_noqa_no_space_after_colon() {
        // "# noqa:E711" (no space after colon) should still work
        let result = parse_noqa(b"# noqa:E711");
        assert_eq!(result, Some(Some(vec!["E711".to_string()])));
    }

    #[test]
    fn test_parse_noqa_inline_after_code() {
        // noqa at end of a code line
        let result = parse_noqa(b"x = 1  # noqa: E711");
        assert_eq!(result, Some(Some(vec!["E711".to_string()])));
    }

    #[test]
    fn test_parse_noqa_colon_but_no_codes() {
        // "# noqa:" with nothing after -> blanket
        assert_eq!(parse_noqa(b"# noqa:"), Some(None));
        assert_eq!(parse_noqa(b"# noqa:  "), Some(None));
    }

    // ─────────────────────────────────────────────────────────────────────
    // compute_style_flags
    // ─────────────────────────────────────────────────────────────────────

    #[test]
    fn test_style_flags_empty() {
        assert_eq!(compute_style_flags(b""), 0);
    }

    #[test]
    fn test_style_flags_simple_assignment() {
        // "x = 1" -- normal spacing, no flags
        assert_eq!(compute_style_flags(b"x = 1"), 0);
    }

    #[test]
    fn test_style_flags_double_space_around_operator() {
        // "x  = 1" -- double space before operator
        let flags = compute_style_flags(b"x  = 1");
        assert_ne!(flags & STYLE_DOUBLE_SPACE_AROUND_OP, 0);
    }

    #[test]
    fn test_style_flags_double_space_after_operator() {
        // "x =  1" -- double space after operator
        let flags = compute_style_flags(b"x =  1");
        assert_ne!(flags & STYLE_DOUBLE_SPACE_AROUND_OP, 0);
    }

    #[test]
    fn test_style_flags_tab_around_operator() {
        // "x\t= 1" -- tab before operator
        let flags = compute_style_flags(b"x\t= 1");
        assert_ne!(flags & STYLE_TAB_AROUND_OP, 0);
    }

    #[test]
    fn test_style_flags_double_space_after_comma() {
        // "a,  b" -- double space after comma
        let flags = compute_style_flags(b"a,  b");
        assert_ne!(flags & STYLE_DOUBLE_SPACE_AFTER_COMMA, 0);
    }

    #[test]
    fn test_style_flags_tab_after_comma() {
        // "a,\tb" -- tab after comma
        let flags = compute_style_flags(b"a,\tb");
        assert_ne!(flags & STYLE_TAB_AFTER_COMMA, 0);
    }

    #[test]
    fn test_style_flags_normal_comma() {
        // "a, b" -- single space after comma, no flags for comma
        let flags = compute_style_flags(b"a, b");
        assert_eq!(flags & STYLE_DOUBLE_SPACE_AFTER_COMMA, 0);
        assert_eq!(flags & STYLE_TAB_AFTER_COMMA, 0);
    }

    #[test]
    fn test_style_flags_keyword_double_space() {
        // "if  True:" -- double space after keyword
        let flags = compute_style_flags(b"if  True:");
        assert_ne!(flags & STYLE_DOUBLE_SPACE_AROUND_KW, 0);
    }

    #[test]
    fn test_style_flags_keyword_tab() {
        // "if\tTrue:" -- tab after keyword
        let flags = compute_style_flags(b"if\tTrue:");
        assert_ne!(flags & STYLE_TAB_AROUND_KW, 0);
    }

    #[test]
    fn test_style_flags_keyword_normal_space() {
        // "if True:" -- single space, no keyword flags
        let flags = compute_style_flags(b"if True:");
        assert_eq!(flags & STYLE_DOUBLE_SPACE_AROUND_KW, 0);
        assert_eq!(flags & STYLE_TAB_AROUND_KW, 0);
    }

    #[test]
    fn test_style_flags_string_literal_ignored() {
        // Double spaces inside a string literal should not set flags
        let flags = compute_style_flags(b"x = '  =  '");
        // The spaces around the outer = are normal (single space)
        // The inner content is inside quotes and should be skipped
        assert_eq!(flags & STYLE_DOUBLE_SPACE_AROUND_OP, 0);
    }

    #[test]
    fn test_style_flags_keyword_not_in_identifier() {
        // "iffy" contains "if" but is not a keyword -- no flags
        let flags = compute_style_flags(b"iffy = 1");
        assert_eq!(flags & STYLE_DOUBLE_SPACE_AROUND_KW, 0);
        assert_eq!(flags & STYLE_TAB_AROUND_KW, 0);
    }

    // ─────────────────────────────────────────────────────────────────────
    // is_op_char / is_ident helpers
    // ─────────────────────────────────────────────────────────────────────

    #[test]
    fn test_is_op_char() {
        for &ch in b"+-*/%=<>!&|^@" {
            assert!(
                is_op_char(ch),
                "expected {:?} to be an operator",
                ch as char
            );
        }
        for &ch in b"a0 ,.(" {
            assert!(
                !is_op_char(ch),
                "expected {:?} not to be an operator",
                ch as char
            );
        }
    }

    #[test]
    fn test_is_ident() {
        for &ch in b"azAZ09_" {
            assert!(is_ident(ch), "expected {:?} to be ident", ch as char);
        }
        for &ch in b" .,+-" {
            assert!(!is_ident(ch), "expected {:?} not to be ident", ch as char);
        }
    }

    // ─────────────────────────────────────────────────────────────────────
    // skip_string
    // ─────────────────────────────────────────────────────────────────────

    #[test]
    fn test_skip_string_single_quoted() {
        // 'hello' starts at 0, should skip to 7 (past closing quote)
        let code = b"'hello' + x";
        assert_eq!(skip_string(code, 0), 7);
    }

    #[test]
    fn test_skip_string_double_quoted() {
        let code = b"\"hello\" + x";
        assert_eq!(skip_string(code, 0), 7);
    }

    #[test]
    fn test_skip_string_with_escape() {
        // 'he\'llo' -- escaped quote inside
        let code = b"'he\\'llo' + x";
        assert_eq!(skip_string(code, 0), 9);
    }

    #[test]
    fn test_skip_string_triple_quoted() {
        let code = b"'''hello world''' + x";
        assert_eq!(skip_string(code, 0), 17);
    }

    #[test]
    fn test_skip_string_unterminated() {
        // Unterminated string returns code.len()
        let code = b"'hello";
        assert_eq!(skip_string(code, 0), code.len());
    }
}
