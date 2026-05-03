use tree_sitter::Language;

#[derive(Clone, Copy)]
pub(crate) struct NodeKinds {
    // Scope-creating
    pub function_definition: u16,
    pub async_function_definition: u16,
    pub class_definition: u16,
    pub lambda: u16,
    pub list_comprehension: u16,
    pub set_comprehension: u16,
    pub dictionary_comprehension: u16,
    pub generator_expression: u16,
    // Statements
    pub assignment: u16,
    pub augmented_assignment: u16,
    pub import_statement: u16,
    pub import_from_statement: u16,
    pub future_import_statement: u16,
    pub for_statement: u16,
    pub async_for_statement: u16,
    pub while_statement: u16,
    pub try_statement: u16,
    pub for_in_clause: u16,
    pub named_expression: u16,
    pub global_statement: u16,
    pub nonlocal_statement: u16,
    pub except_clause: u16,
    pub with_item: u16,
    pub case_clause: u16,
    pub with_statement: u16,
    pub async_with_statement: u16,
    pub finally_clause: u16,
    pub break_statement: u16,
    pub continue_statement: u16,
    pub return_statement: u16,
    pub yield_expr: u16,
    pub yield_statement: u16,
    // Leaf
    pub identifier: u16,
    // Import sub-nodes
    pub dotted_name: u16,
    pub aliased_import: u16,
    pub relative_import: u16,
    pub wildcard_import: u16,
    // Patterns
    pub as_pattern: u16,
    pub as_pattern_target: u16,
    pub case_pattern: u16,
    // Parameters
    pub parameters: u16,
    pub lambda_parameters: u16,
    pub typed_parameter: u16,
    pub default_parameter: u16,
    pub typed_default_parameter: u16,
    pub list_splat_pattern: u16,
    pub dictionary_splat_pattern: u16,
    // Containers
    pub tuple: u16,
    pub list: u16,
    pub tuple_pattern: u16,
    pub list_pattern: u16,
    pub pattern_list: u16,
    // Literals
    pub string: u16,
    pub comment: u16,
    // Binding context
    pub attribute: u16,
    pub keyword_argument: u16,
    pub with_clause: u16,
}

impl NodeKinds {
    pub fn new(lang: &Language) -> Self {
        let nk = |name: &str| {
            let id = lang.id_for_node_kind(name, true);
            debug_assert!(id != 0, "unknown node kind: {name}");
            id
        };
        Self {
            function_definition: nk("function_definition"),
            async_function_definition: nk("async_function_definition"),
            class_definition: nk("class_definition"),
            lambda: nk("lambda"),
            list_comprehension: nk("list_comprehension"),
            set_comprehension: nk("set_comprehension"),
            dictionary_comprehension: nk("dictionary_comprehension"),
            generator_expression: nk("generator_expression"),
            assignment: nk("assignment"),
            augmented_assignment: nk("augmented_assignment"),
            import_statement: nk("import_statement"),
            import_from_statement: nk("import_from_statement"),
            future_import_statement: nk("future_import_statement"),
            for_statement: nk("for_statement"),
            async_for_statement: nk("async_for_statement"),
            while_statement: nk("while_statement"),
            try_statement: nk("try_statement"),
            for_in_clause: nk("for_in_clause"),
            named_expression: nk("named_expression"),
            global_statement: nk("global_statement"),
            nonlocal_statement: nk("nonlocal_statement"),
            except_clause: nk("except_clause"),
            with_item: nk("with_item"),
            case_clause: nk("case_clause"),
            with_statement: nk("with_statement"),
            async_with_statement: nk("async_with_statement"),
            finally_clause: nk("finally_clause"),
            break_statement: nk("break_statement"),
            continue_statement: nk("continue_statement"),
            return_statement: nk("return_statement"),
            yield_expr: nk("yield"),
            yield_statement: nk("yield_statement"),
            identifier: nk("identifier"),
            dotted_name: nk("dotted_name"),
            aliased_import: nk("aliased_import"),
            relative_import: nk("relative_import"),
            wildcard_import: nk("wildcard_import"),
            as_pattern: nk("as_pattern"),
            as_pattern_target: nk("as_pattern_target"),
            case_pattern: nk("case_pattern"),
            parameters: nk("parameters"),
            lambda_parameters: nk("lambda_parameters"),
            typed_parameter: nk("typed_parameter"),
            default_parameter: nk("default_parameter"),
            typed_default_parameter: nk("typed_default_parameter"),
            list_splat_pattern: nk("list_splat_pattern"),
            dictionary_splat_pattern: nk("dictionary_splat_pattern"),
            tuple: nk("tuple"),
            list: nk("list"),
            tuple_pattern: nk("tuple_pattern"),
            list_pattern: nk("list_pattern"),
            pattern_list: nk("pattern_list"),
            string: nk("string"),
            comment: nk("comment"),
            attribute: nk("attribute"),
            keyword_argument: nk("keyword_argument"),
            with_clause: nk("with_clause"),
        }
    }
}

#[derive(Clone, Copy)]
pub(crate) struct FieldIds {
    pub name: u16,
    pub left: u16,
    pub right: u16,
    pub parameters: u16,
    pub type_: u16,
    pub alias: u16,
    pub attribute: u16,
}

impl FieldIds {
    pub fn new(lang: &Language) -> Result<Self, String> {
        let fid = |name: &str| -> Result<u16, String> {
            lang.field_id_for_name(name)
                .map(|id| id.get())
                .ok_or_else(|| {
                    format!(
                        "unknown field name '{name}' in tree-sitter-python grammar; \
                         the grammar version may be incompatible"
                    )
                })
        };
        Ok(Self {
            name: fid("name")?,
            left: fid("left")?,
            right: fid("right")?,
            parameters: fid("parameters")?,
            type_: fid("type")?,
            alias: fid("alias")?,
            attribute: fid("attribute")?,
        })
    }
}
