"""Aggregate probe. Records the raw manifest the platform passes in."""
import argparse
import json
import os

DEFAULT_OUTPUT_NAME = "aggregate_probe.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.manifest, "r", encoding="utf-8", errors="replace") as handle:
        raw = handle.read()

    try:
        parsed = json.loads(raw)
        shape = type(parsed).__name__
        keys = list(parsed.keys()) if isinstance(parsed, dict) else None
    except ValueError:
        parsed, shape, keys = None, "not-json", None

    record = {
        "manifest_path": args.manifest,
        "manifest_shape": shape,
        "top_level_keys": keys,
        "raw_manifest": raw[:20000],
        "working_dir_listing": sorted(os.listdir(os.path.dirname(os.path.abspath(args.manifest)) or ".")),
    }

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)


if __name__ == "__main__":
    main()
