import unittest

import context  # noqa: F401
from dep_utils.idparse import find_ids, find_ids_with_stats


def canon(text):
    return [i["canonical"] for i in find_ids(text)]


class IdParseTests(unittest.TestCase):
    def test_plain_three_segment_id(self):
        self.assertEqual(canon("per SOP-MNT-009 section 4"), ["SOP-MNT-009"])

    def test_two_segment_id(self):
        self.assertEqual(canon("see WI-203"), ["WI-203"])

    def test_lowercase_known_prefix_is_repaired(self):
        found = find_ids("follow sop-mnt-9 first")
        self.assertEqual(found[0]["canonical"], "SOP-MNT-009")
        self.assertEqual(found[0]["confidence"], "normalised")

    def test_exact_id_has_exact_confidence(self):
        self.assertEqual(find_ids("SOP-MNT-009")[0]["confidence"], "exact")

    def test_en_dash_and_underscore_separators(self):
        self.assertEqual(canon("SOP\u2013MNT\u2013014 and FRM_MNT_221"), ["SOP-MNT-014", "FRM-MNT-221"])

    def test_stoplisted_prefixes_are_skipped_and_counted(self):
        found, stoplisted = find_ids_with_stats("ISO-9001, UTF-8 and COVID-19")
        self.assertEqual(found, [])
        self.assertEqual(stoplisted, 3)

    def test_placeholder_is_not_a_document(self):
        self.assertEqual(canon("use SOP-XXX-000 as a template"), [])

    def test_unlisted_prefix_needs_two_digits(self):
        self.assertEqual(canon("ABC-5"), [])
        self.assertEqual(canon("ABC-55"), ["ABC-055"])

    def test_ordinary_words_are_not_ids(self):
        self.assertEqual(canon("of SOP 12 and step-1 and Step 3"), [])

    def test_revision_and_section_do_not_change_the_id(self):
        item = find_ids("SOP-MNT-009 Rev C section 4.2 applies")[0]
        self.assertEqual(item["canonical"], "SOP-MNT-009")
        self.assertEqual(item["revision"], "C")
        self.assertEqual(item["section"], "4.2")

    def test_id_followed_by_more_digits_segment_is_not_split(self):
        self.assertEqual(canon("CVE-2024-1234"), [])

    def test_unlisted_prefix_with_lowercase_middle_is_rejected(self):
        self.assertEqual(canon("ABC-def-55"), [])


if __name__ == "__main__":
    unittest.main()
