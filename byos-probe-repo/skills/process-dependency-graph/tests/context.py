"""Shared paths for the tests. Run from the skill folder: python3 -m unittest discover -s tests"""
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(os.path.dirname(TESTS_DIR), "scripts")
PAGES_DIR = os.path.join(TESTS_DIR, "fixtures", "pages")

if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)


def read_page(name):
    with open(os.path.join(PAGES_DIR, name), "r", encoding="utf-8") as handle:
        return handle.read()


def parse_fixture(name):
    from dep_utils.pageparse import parse_page
    return parse_page(read_page(name), fallback_name=os.path.splitext(name)[0])


def targets(record, relation=None, kind=None):
    return sorted(r["target"] for r in record["refs"]
                  if (relation is None or r["relation"] == relation) and (kind is None or r["kind"] == kind))
