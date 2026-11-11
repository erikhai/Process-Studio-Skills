"""Per-page probe. Records what the platform passes in for one wiki page."""
import argparse
import json
import re

DEFAULT_OUTPUT_NAME = "probe.json"

ID_PATTERN = re.compile(r"\b(?:SOP|FRM|WI|POL)-[A-Z]{2,4}-\d{3}\b")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8", errors="replace") as handle:
        text = handle.read()

    ids = ID_PATTERN.findall(text)
    first_id_pos = {}
    for match in ID_PATTERN.finditer(text):
        first_id_pos.setdefault(match.group(0), match.start())

    record = {
        "input_path": args.input,
        "chars": len(text),
        "lines": text.count("\n") + 1,
        "headings": [ln for ln in text.splitlines() if ln.startswith("#")][:20],
        "ids_found": sorted(set(ids)),
        "id_mentions": len(ids),
        "last_id_char_position": max(first_id_pos.values()) if first_id_pos else None,
        "starts_with": text[:300],
        "ends_with": text[-300:],
    }

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)


if __name__ == "__main__":
    main()
