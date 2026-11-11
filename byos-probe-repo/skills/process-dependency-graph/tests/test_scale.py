import random
import time
import unittest

import context  # noqa: F401
from dep_utils.analysis import analyse
from dep_utils.graph import build_graph
from dep_utils.pageparse import parse_page
from dep_utils.render import render_report


def synthetic_corpus(size, seed=7):
    rng = random.Random(seed)
    pages = []
    for i in range(size):
        lines = ["# SOP-SCL-%04d Synthetic procedure %d" % (i, i), "", "## Steps"]
        for _ in range(rng.randint(1, 6)):
            target = rng.randrange(0, size + 20)  # some targets are missing from the corpus
            lines.append("1. Follow SOP-SCL-%04d and record in SAP PM." % target)
        pages.append("\n".join(lines))
    return pages


class ScaleTests(unittest.TestCase):
    def test_about_1400_documents_complete_quickly(self):
        started = time.time()
        records = [parse_page(text, "p%d" % i) for i, text in enumerate(synthetic_corpus(1400))]
        graph = build_graph(records)
        analysis = analyse(graph)
        report = render_report(graph, analysis)
        elapsed = time.time() - started
        self.assertLess(elapsed, 30)
        self.assertEqual(len([n for n in graph["nodes"].values() if n["kind"] == "document"]), 1400)
        self.assertIn("```mermaid", report)
        self.assertLess(report.count("\n"), 2000)

    def test_blast_radius_matches_brute_force_on_a_random_graph(self):
        records = [parse_page(text, "p%d" % i) for i, text in enumerate(synthetic_corpus(120, seed=3))]
        graph = build_graph(records)
        analysis = analyse(graph)
        in_adj = analysis["in_adj"]
        for node in list(graph["nodes"])[:60]:
            seen, queue = set(), [node]
            while queue:
                current = queue.pop()
                for dependent in in_adj[current]:
                    if dependent not in seen and dependent != node:
                        seen.add(dependent)
                        queue.append(dependent)
            self.assertEqual(analysis["metrics"][node]["blast"], len(seen), node)


if __name__ == "__main__":
    unittest.main()
