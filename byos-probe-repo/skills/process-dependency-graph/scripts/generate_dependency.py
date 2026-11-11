"""Per-page step: read one wiki page and record its document ID and references."""
import argparse
import json
import os
import sys

DEFAULT_OUTPUT_NAME = "dependency.json"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dep_utils.pageparse import SCHEMA_VERSION, parse_page  # noqa: E402


def run(input_path, output_path):
    fallback = os.path.splitext(os.path.basename(input_path))[0]
    try:
        with open(input_path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        record = parse_page(text, fallback_name=fallback)
    except Exception as error:  # a bad page must not fail the batch
        record = {
            "schema_version": SCHEMA_VERSION, "doc_id": "NOID-" + fallback.upper(),
            "doc_id_source": "slug-fallback", "doc_type": "document", "title": None, "chars": 0,
            "truncated_suspected": False, "refs": [], "lineage": [],
            "ignored": {"self_references": 0, "change_log_references": 0,
                        "lineage_references": 0, "stoplisted_ids": 0},
            "warnings": ["page could not be parsed: " + type(error).__name__],
        }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    run(args.input, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
