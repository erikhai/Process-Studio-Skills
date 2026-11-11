import glob
import json
import os
import re
import shutil
import tempfile
import unittest

import context
from context import PAGES_DIR

import generate_aggregate_dependency_graph as aggregate
import generate_dependency as per_page
from dep_utils import config

CORE = ["SOP-MNT-009_Work_Order_Creation.md", "SOP-MNT-014_Corrective_Closure.md",
        "SOP-QA-031_Quality_Hold.md", "FRM-MNT-221_Closure_Form.md",
        "SOP-MNT-050_Long_Shutdown_Planning.md"]


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.outputs = []
        for name in CORE:
            out = os.path.join(self.tmp, os.path.splitext(name)[0] + "-dependency.json")
            self.assertEqual(per_page.main(["--input", os.path.join(PAGES_DIR, name), "--output", out]), 0)
            self.outputs.append(out)

    def run_aggregate(self, manifest_obj, as_text=False):
        manifest = os.path.join(self.tmp, "manifest.json")
        with open(manifest, "w", encoding="utf-8") as handle:
            handle.write(manifest_obj if as_text else json.dumps(manifest_obj))
        report = os.path.join(self.tmp, "report.md")
        self.assertEqual(aggregate.main(["--manifest", manifest, "--output", report]), 0)
        with open(report, "r", encoding="utf-8") as handle:
            return handle.read()

    def check_report(self, text):
        self.assertIn("# Process dependency graph", text)
        self.assertIn("5 documents analysed", text)
        self.assertIn("changing `FRM-MNT-221` may affect 4 documents", text)
        self.assertIn("## Relationship evidence", text)
        self.assertIn("| From → to | Source page | Line | Section | Page mentions | Edge total | Confidence | Captured context |", text)
        self.assertRegex(text, r"`SOP-MNT-014` → `FRM-MNT-221`.*SOP-MNT-014")
        self.assertIn("```mermaid", text)
        match = re.search(r"```json\n(.*?)\n```", text, re.S)
        data = json.loads(match.group(1))
        self.assertEqual(len([n for n in data["nodes"] if n["kind"] == "document"]), 5)

    def test_manifest_as_list_of_paths(self):
        self.check_report(self.run_aggregate(self.outputs))

    def test_manifest_as_list_of_objects(self):
        self.check_report(self.run_aggregate([{"page": "p", "output_path": o} for o in self.outputs]))

    def test_manifest_wrapped_in_object(self):
        self.check_report(self.run_aggregate({"pages": {"outputs": self.outputs}}))

    def test_manifest_with_relative_file_names(self):
        self.check_report(self.run_aggregate([os.path.basename(o) for o in self.outputs]))

    def test_manifest_as_plain_text_list(self):
        self.check_report(self.run_aggregate("\n".join(self.outputs) + "\n", as_text=True))

    def test_unusable_manifest_falls_back_to_scanning(self):
        text = self.run_aggregate({"unexpected": "shape"})
        self.check_report(text)
        self.assertIn("scanned nearby folders", text)

    def test_missing_pages_do_not_crash_the_run(self):
        text = self.run_aggregate(self.outputs[:2] + [os.path.join(self.tmp, "gone.json")])
        self.assertIn("# Process dependency graph", text)

    def test_empty_corpus_produces_a_report(self):
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        manifest = os.path.join(empty, "manifest.json")
        with open(manifest, "w") as handle:
            handle.write("[]")
        report = os.path.join(empty, "report.md")
        self.assertEqual(aggregate.main(["--manifest", manifest, "--output", report]), 0)
        with open(report) as handle:
            self.assertIn("no references were found", handle.read())

    def test_sidecars_are_written_only_when_switched_on(self):
        self.run_aggregate(self.outputs)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "dependency_graph.json")))
        config.WRITE_SIDECARS = True
        self.addCleanup(setattr, config, "WRITE_SIDECARS", False)
        self.run_aggregate(self.outputs)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "dependency_graph.json")))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "dependency_graph.mmd")))

    def test_report_is_identical_across_runs(self):
        first = self.run_aggregate(self.outputs)
        second = self.run_aggregate(list(reversed(self.outputs)))
        self.assertEqual(first, second)

    def test_evidence_rows_are_bounded_for_large_reports(self):
        from dep_utils.analysis import analyse
        from dep_utils.graph import build_graph
        from dep_utils.pageparse import parse_page
        from dep_utils.render import render_report
        old_limit = config.EVIDENCE_MAX_ROWS
        self.addCleanup(setattr, config, "EVIDENCE_MAX_ROWS", old_limit)
        config.EVIDENCE_MAX_ROWS = 1
        graph = build_graph([
            parse_page("# SOP-EVD-001 Source\nSee SOP-EVD-002 and SOP-EVD-003.\n"),
            parse_page("# SOP-EVD-002 First\n"),
            parse_page("# SOP-EVD-003 Second\n"),
        ])
        text = render_report(graph, analyse(graph))
        self.assertIn("Showing the first 1 of 2 captured evidence rows", text)

    def test_per_page_script_survives_missing_and_binary_input(self):
        out = os.path.join(self.tmp, "x-dependency.json")
        self.assertEqual(per_page.main(["--input", os.path.join(self.tmp, "nope.md"), "--output", out]), 0)
        with open(out) as handle:
            self.assertTrue(json.load(handle)["warnings"])
        binary = os.path.join(self.tmp, "bin.md")
        with open(binary, "wb") as handle:
            handle.write(bytes(range(256)) * 20)
        self.assertEqual(per_page.main(["--input", binary, "--output", out]), 0)

    def test_scripts_declare_default_output_name_near_the_top(self):
        for name, expected in (("generate_dependency.py", ".json"),
                               ("generate_aggregate_dependency_graph.py", ".md")):
            with open(os.path.join(context.SCRIPTS_DIR, name), encoding="utf-8") as handle:
                head = handle.read(3000)
            first = [ln for ln in head.splitlines() if "output" in ln.lower()][0]
            self.assertIn("DEFAULT_OUTPUT_NAME", first)
            self.assertIn(expected, first)

    def test_records_and_graph_json_match_the_schema_required_keys(self):
        with open(os.path.join(os.path.dirname(context.SCRIPTS_DIR), "schema.json")) as handle:
            definitions = json.load(handle)["definitions"]
        with open(self.outputs[0]) as handle:
            record = json.load(handle)
        self.assertTrue(set(definitions["page_record"]["required"]) <= set(record))
        for ref in record["refs"]:
            self.assertTrue(set(definitions["reference"]["required"]) <= set(ref))
        text = self.run_aggregate(self.outputs)
        data = json.loads(re.search(r"```json\n(.*?)\n```", text, re.S).group(1))
        for node in data["nodes"]:
            self.assertTrue(set(definitions["graph"]["properties"]["nodes"]["items"]["required"]) <= set(node))
        for edge in data["edges"]:
            self.assertTrue(set(definitions["graph"]["properties"]["edges"]["items"]["required"]) <= set(edge))

    def test_manifest_json_declares_both_scripts(self):
        with open(os.path.join(context.SCRIPTS_DIR, "manifest.json")) as handle:
            declared = json.load(handle)["scripts"]
        scripts = {os.path.basename(p) for p in glob.glob(os.path.join(context.SCRIPTS_DIR, "generate_*.py"))}
        self.assertEqual(set(declared), scripts)


if __name__ == "__main__":
    unittest.main()
