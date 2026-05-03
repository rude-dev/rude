use criterion::{BenchmarkId, Criterion, Throughput, criterion_group, criterion_main};
use rude::bench_api::{compute_line_infos, compute_style_flags, do_analyze_result};
use rustc_hash::FxHashSet;
use std::path::Path;
use tree_sitter::Parser;

fn load_corpus(name: &str) -> Vec<(String, Vec<u8>)> {
    let dir = Path::new("benches/corpus").join(name);
    let mut files = Vec::new();
    visit_dir(&dir, &mut files);
    files
}

fn visit_dir(dir: &Path, files: &mut Vec<(String, Vec<u8>)>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            visit_dir(&path, files);
        } else if path.extension().is_some_and(|e| e == "py")
            && let Ok(bytes) = std::fs::read(&path)
        {
            files.push((path.display().to_string(), bytes));
        }
    }
}

fn make_parser() -> Parser {
    let mut parser = Parser::new();
    parser
        .set_language(&tree_sitter_python::LANGUAGE.into())
        .expect("failed to set python language");
    parser
}

fn bench_do_analyze_result(c: &mut Criterion) {
    let mut group = c.benchmark_group("analyze");
    let mut parser = make_parser();

    for name in ["large"] {
        let corpus = load_corpus(name);
        if corpus.is_empty() {
            eprintln!(
                "Skipping {name}: corpus not found (run: uv run python benches/corpus/download.py {name})"
            );
            continue;
        }
        let total_bytes: u64 = corpus.iter().map(|(_, b)| b.len() as u64).sum();
        group.throughput(Throughput::Bytes(total_bytes));
        group.bench_with_input(BenchmarkId::new("corpus", name), &corpus, |b, files| {
            b.iter(|| {
                for (_, source) in files {
                    let tree = parser.parse(source, None).unwrap();
                    std::hint::black_box(do_analyze_result(source, tree.root_node(), &None));
                }
            });
        });
    }
    group.finish();
}

fn bench_compute_line_infos(c: &mut Criterion) {
    let mut group = c.benchmark_group("line_infos");
    let empty_strings: FxHashSet<u32> = FxHashSet::default();

    for name in ["large"] {
        let corpus = load_corpus(name);
        if corpus.is_empty() {
            continue;
        }
        let total_bytes: u64 = corpus.iter().map(|(_, b)| b.len() as u64).sum();
        group.throughput(Throughput::Bytes(total_bytes));
        group.bench_with_input(BenchmarkId::new("corpus", name), &corpus, |b, files| {
            b.iter(|| {
                for (_, source) in files {
                    std::hint::black_box(compute_line_infos(source, &empty_strings));
                }
            });
        });
    }
    group.finish();
}

fn bench_compute_style_flags(c: &mut Criterion) {
    let path = "benches/corpus/large/conf/global_settings.py";
    let Ok(source) = std::fs::read(path) else {
        eprintln!("Skipping style_flags: {path} not found");
        return;
    };
    let lines: Vec<&[u8]> = source.split(|&b| b == b'\n').collect();

    c.bench_function("style_flags/global_settings", |b| {
        b.iter(|| {
            for line in &lines {
                std::hint::black_box(compute_style_flags(line));
            }
        });
    });
}

criterion_group!(
    benches,
    bench_do_analyze_result,
    bench_compute_line_infos,
    bench_compute_style_flags
);
criterion_main!(benches);
