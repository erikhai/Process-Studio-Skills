import unittest

import context
from context import parse_fixture, targets


class PageParseTests(unittest.TestCase):
    def test_own_id_comes_from_h1(self):
        record = parse_fixture("SOP-MNT-014_Corrective_Closure.md")
        self.assertEqual(record["doc_id"], "SOP-MNT-014")
        self.assertEqual(record["doc_id_source"], "h1")
        self.assertEqual(record["title"], "Corrective Work Order Closure")

    def test_references_and_systems_in_a_procedure(self):
        record = parse_fixture("SOP-MNT-014_Corrective_Closure.md")
        self.assertEqual(targets(record, kind="procedure"), ["SOP-MNT-009", "SOP-QA-031"])
        self.assertEqual(targets(record, kind="form"), ["FRM-MNT-221"])
        self.assertEqual(targets(record, kind="system"), ["SAP PM"])
        section = [r for r in record["refs"] if r["target"] == "SOP-MNT-009"][0]["section"]
        self.assertEqual(section, "4")

    def test_used_by_sentence_inverts_direction(self):
        record = parse_fixture("FRM-MNT-221_Closure_Form.md")
        self.assertEqual(targets(record, relation="depended_on_by"), ["SOP-MNT-009", "SOP-MNT-014"])
        self.assertEqual(targets(record, relation="depends_on"), [])

    def test_used_by_phrase_must_sit_next_to_the_id(self):
        from dep_utils.pageparse import parse_page
        record = parse_page("# SOP-AAA-001 X\n\nUsed by planners when following SOP-MNT-009.\n")
        self.assertEqual(targets(record, relation="depends_on"), ["SOP-MNT-009"])

    def test_heading_sets_direction_for_the_section(self):
        record = parse_fixture("edge_usedby.md")
        self.assertEqual(targets(record, relation="depended_on_by"),
                         ["SOP-MNT-014", "SOP-MNT-050", "SOP-QA-031"])

    def test_malformed_ids_are_repaired(self):
        record = parse_fixture("edge_malformed.md")
        self.assertEqual(record["doc_id"], "SOP-MNT-020")
        self.assertEqual(targets(record, kind="procedure"), ["SOP-MNT-009", "SOP-MNT-014"])
        self.assertEqual(targets(record, kind="form"), ["FRM-MNT-221"])
        self.assertGreaterEqual(record["ignored"]["stoplisted_ids"], 3)

    def test_page_without_id_gets_placeholder(self):
        record = parse_fixture("edge_noid.md")
        self.assertEqual(record["doc_id_source"], "slug-fallback")
        self.assertTrue(record["doc_id"].startswith("NOID-"))
        self.assertTrue(any("no document ID" in w for w in record["warnings"]))
        self.assertEqual(targets(record), ["SOP-MNT-009"])

    def test_self_reference_is_dropped_and_counted(self):
        record = parse_fixture("edge_selfref.md")
        self.assertEqual(targets(record), ["SOP-MNT-009"])
        self.assertEqual(record["ignored"]["self_references"], 1)

    def test_change_log_and_lineage_do_not_create_references(self):
        record = parse_fixture("edge_changelog.md")
        self.assertEqual(targets(record), ["FRM-MNT-221", "SOP-MNT-009"])
        self.assertEqual(record["ignored"]["change_log_references"], 1)
        self.assertEqual(record["lineage"], ["SOP-OLD-005"])

    def test_frontmatter_id_and_system(self):
        record = parse_fixture("edge_frontmatter.md")
        self.assertEqual(record["doc_id"], "WI-MNT-100")
        self.assertEqual(record["doc_id_source"], "frontmatter")
        self.assertEqual(targets(record, kind="procedure"), ["WI-MNT-101"])
        self.assertEqual(targets(record, kind="system"), ["Maximo"])

    def test_long_page_is_flagged_and_late_reference_found_locally(self):
        record = parse_fixture("SOP-MNT-050_Long_Shutdown_Planning.md")
        self.assertTrue(record["truncated_suspected"])
        self.assertEqual(targets(record, kind="procedure"), ["SOP-MNT-014", "SOP-MNT-999"])

    def test_empty_page_does_not_crash(self):
        from dep_utils.pageparse import parse_page
        record = parse_page("", fallback_name="blank")
        self.assertEqual(record["refs"], [])
        self.assertIn("page is empty", record["warnings"])

    def test_system_inside_an_id_is_not_a_system(self):
        from dep_utils.pageparse import parse_page
        record = parse_page("# SOP-AAA-001 X\n\nSee SAP-FIN-001 for details.\n")
        self.assertEqual(targets(record, kind="system"), [])


if __name__ == "__main__":
    unittest.main()
