import glob
import os
import unittest

import context
from context import PAGES_DIR, parse_fixture
from dep_utils.analysis import analyse, strongly_connected
from dep_utils.graph import build_graph

CORE = ["SOP-MNT-009_Work_Order_Creation.md", "SOP-MNT-014_Corrective_Closure.md",
        "SOP-QA-031_Quality_Hold.md", "FRM-MNT-221_Closure_Form.md",
        "SOP-MNT-050_Long_Shutdown_Planning.md"]


def core_graph():
    return build_graph([parse_fixture(name) for name in CORE])


class CoreCorpusTests(unittest.TestCase):
    def setUp(self):
        self.graph = core_graph()
        self.analysis = analyse(self.graph)
        self.metrics = self.analysis["metrics"]

    def test_nodes(self):
        kinds = {n: v["kind"] for n, v in self.graph["nodes"].items()}
        self.assertEqual(sum(1 for k in kinds.values() if k == "document"), 5)
        self.assertEqual(kinds["SOP-MNT-999"], "unresolved")
        self.assertEqual(kinds["SAP PM"], "system")

    def test_cycle_excludes_the_form(self):
        self.assertEqual(len(self.analysis["cycles"]), 1)
        self.assertEqual(self.analysis["cycles"][0]["members"],
                         ["SOP-MNT-009", "SOP-MNT-014", "SOP-QA-031"])
        self.assertIsNone(self.metrics["FRM-MNT-221"]["cycle"])

    def test_blast_radius(self):
        expected = {"FRM-MNT-221": 4, "SAP PM": 4, "SOP-MNT-009": 3, "SOP-MNT-014": 3,
                    "SOP-QA-031": 3, "SOP-MNT-999": 1, "SOP-MNT-050": 0}
        self.assertEqual({k: self.metrics[k]["blast"] for k in expected}, expected)

    def test_direct_dependents(self):
        self.assertEqual(self.metrics["SOP-MNT-014"]["dependents"], 2)
        self.assertEqual(self.metrics["FRM-MNT-221"]["dependents"], 2)

    def test_unresolved_reference(self):
        self.assertEqual([u["id"] for u in self.analysis["unresolved"]], ["SOP-MNT-999"])
        self.assertEqual(self.analysis["unresolved"][0]["cited_by"], ["SOP-MNT-050"])

    def test_tiers(self):
        self.assertEqual(self.analysis["tiers"], [
            [["FRM-MNT-221"]],
            [["SOP-MNT-009", "SOP-MNT-014", "SOP-QA-031"]],
            [["SOP-MNT-050"]],
        ])

    def test_ranking_is_by_blast_then_dependents_then_id(self):
        self.assertEqual(self.analysis["ranking"][0], "FRM-MNT-221")
        self.assertEqual(self.analysis["ranking"][-1], "SOP-MNT-050")

    def test_system_hub(self):
        self.assertEqual(self.analysis["systems"][0]["id"], "SAP PM")
        self.assertEqual(len(self.analysis["systems"][0]["dependents"]), 3)

    def test_truncation_is_counted(self):
        self.assertEqual(self.graph["stats"]["truncated_pages"], 1)

    def test_results_are_repeatable(self):
        again = analyse(core_graph())
        self.assertEqual(again["ranking"], self.analysis["ranking"])
        self.assertEqual(again["tiers"], self.analysis["tiers"])


class EdgeCaseGraphTests(unittest.TestCase):
    def setUp(self):
        records = [parse_fixture(os.path.basename(p))
                   for p in sorted(glob.glob(os.path.join(PAGES_DIR, "*.md")))]
        self.graph = build_graph(records)
        self.analysis = analyse(self.graph)

    def test_duplicate_ids_are_merged_with_a_warning(self):
        self.assertEqual(self.graph["stats"]["duplicate_ids"], ["SOP-DUP-001"])
        self.assertTrue(any("SOP-DUP-001" in w for w in self.graph["warnings"]))

    def test_reverse_direction_page_creates_edges_towards_it(self):
        self.assertIn(("SOP-MNT-014", "SOP-USE-001"), self.graph["edges"])
        self.assertIn(("SOP-QA-031", "SOP-USE-001"), self.graph["edges"])

    def test_isolated_document_is_an_orphan(self):
        self.assertIn("SOP-ISO-001", self.analysis["orphans"])

    def test_normalised_references_are_counted(self):
        self.assertGreaterEqual(self.graph["stats"]["normalised_refs"], 2)


class StronglyConnectedTests(unittest.TestCase):
    def test_deep_chain_does_not_hit_recursion_limit(self):
        nodes = ["n%05d" % i for i in range(5000)]
        adjacency = {nodes[i]: [nodes[i + 1]] for i in range(len(nodes) - 1)}
        components = strongly_connected(nodes, adjacency)
        self.assertEqual(len(components), 5000)

    def test_two_node_cycle(self):
        components = strongly_connected(["a", "b", "c"], {"a": ["b"], "b": ["a"], "c": ["a"]})
        self.assertIn(["a", "b"], components)


if __name__ == "__main__":
    unittest.main()
