"""Aggregate step: merge the per-page records into one dependency graph report."""
import argparse
import os
import sys

DEFAULT_OUTPUT_NAME = "dependency_graph_report.md"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dep_utils import config  # noqa: E402
from dep_utils.analysis import analyse  # noqa: E402
from dep_utils.graph import build_graph, load_records  # noqa: E402
from dep_utils.render import diagram_nodes, graph_json, mermaid_text, render_report  # noqa: E402


def run(manifest_path, output_path):
    records, load_warnings = load_records(manifest_path)
    graph = build_graph(records)
    graph["warnings"] = load_warnings + graph["warnings"]
    analysis = analyse(graph)
    report = render_report(graph, analysis)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(report)

    if config.WRITE_SIDECARS:
        import json
        folder = os.path.dirname(os.path.abspath(output_path))
        selected, edges = diagram_nodes(graph, analysis)
        try:
            with open(os.path.join(folder, "dependency_graph.json"), "w", encoding="utf-8") as handle:
                json.dump(graph_json(graph, analysis), handle, indent=1, sort_keys=True)
            with open(os.path.join(folder, "dependency_graph.mmd"), "w", encoding="utf-8") as handle:
                handle.write(mermaid_text(graph, analysis, selected, edges) + "\n")
        except OSError:
            pass  # the report is the guaranteed deliverable


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    run(args.manifest, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
