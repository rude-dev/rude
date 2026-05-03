use criterion::{Criterion, criterion_group, criterion_main};
use rude::bench_api::{collect_grouped_nodes, find_comment_start_bytes};
use rustc_hash::FxHashMap;
use tree_sitter::Parser;

fn make_parser() -> Parser {
    let mut parser = Parser::new();
    parser
        .set_language(&tree_sitter_python::LANGUAGE.into())
        .expect("failed to set python language");
    parser
}

fn bench_collect_grouped_nodes(c: &mut Criterion) {
    let mut parser = make_parser();
    let path = "benches/corpus/large/conf/global_settings.py";
    let Ok(source) = std::fs::read(path) else {
        eprintln!("Skipping grouping: {path} not found");
        return;
    };
    let tree = parser.parse(&source, None).unwrap();
    let lang: tree_sitter::Language = tree_sitter_python::LANGUAGE.into();

    c.bench_function("grouping/global_settings", |b| {
        b.iter(|| {
            let mut groups = FxHashMap::default();
            collect_grouped_nodes(tree.root_node(), 0, &lang, &None, &mut groups);
            std::hint::black_box(&groups);
        });
    });
}

fn bench_find_comment_start(c: &mut Criterion) {
    let path = "benches/corpus/large/conf/global_settings.py";
    let Ok(source) = std::fs::read(path) else {
        eprintln!("Skipping find_comment_start: {path} not found");
        return;
    };
    let lines: Vec<&[u8]> = source.split(|&b| b == b'\n').collect();

    c.bench_function("find_comment_start/global_settings", |b| {
        b.iter(|| {
            for line in &lines {
                std::hint::black_box(find_comment_start_bytes(line));
            }
        });
    });
}

criterion_group!(
    benches,
    bench_collect_grouped_nodes,
    bench_find_comment_start
);
criterion_main!(benches);
