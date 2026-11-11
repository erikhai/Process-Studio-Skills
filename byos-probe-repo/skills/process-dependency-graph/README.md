# Process dependency graph

A Process Studio BYOS batch skill that shows how procedures depend on each other, so you can decide which ones to change first and see what each change affects.

Version 0.1. Python standard library only. No model calls. No client data inside.

## Who uses it, and when
A transformation lead or process analyst, after a set of SOPs, work instructions and forms has been ingested and before choosing which procedures to redesign first.

**What changes for them:** instead of guessing which procedure is safe to change first, they get a ranked list with an exact count of the documents each change could affect, the cycles that need a human decision, and the documents that are cited but missing.

## What it does
1. **Per page** (`scripts/generate_dependency.py`): reads one wiki page and writes a small JSON record with the page's own document ID and every reference to another document, form or system.
2. **Once at the end** (`scripts/generate_aggregate_dependency_graph.py`): merges all records into one graph and writes `dependency_graph_report.md`.

## How to run it
1. Ingest the documents with **Full document text on wiki** switched on. Only about the first 32,000 characters of a document stay on its wiki page, so references past that point can be lost. The report flags pages near that limit.
2. In Settings, Skills, connect the repository. Folder is the folder that contains this skill's folder (`byos-probe-repo/skills` in the test repository).
3. Sync, check the skill is green and not filtered, then assign it in Project Skills.
4. In the Analyze tab, pick **process-dependency-graph** and run it.
5. Open `dependency_graph_report.md`.

Test on 3 to 5 pages before a full run.

## Input
Wiki pages that are procedures, work instructions or forms and that cite each other by ID.

- The page's own ID is taken from, in order: frontmatter (`doc_id`, `id`, and similar), the first heading, a labelled line such as `Document ID: SOP-MNT-014`, a short first line.
- If no ID is found the page gets a placeholder (`NOID-...`) and a warning, and still appears in the report.
- Pages are never rejected. A page that cannot be read produces a record with a warning so the batch continues.

## Output
One Markdown file with these sections, in this order:

| Section | What it tells you |
|---|---|
| Summary | Highest-risk documents, cycles, missing documents, suggested order, a confidence note |
| Most depended-on documents | Ranked table: direct dependents, blast radius, direct dependencies, cycle, tier |
| What a change touches | For the top documents, which documents cite them directly |
| Cycles | Documents that depend on each other, with the links that form the cycle |
| Missing documents | IDs cited but not in the corpus, and who cites them |
| Suggested change order | Tiers: tier 0 depends on no other document |
| Systems | Which procedures depend on which systems (for example SAP PM) |
| Orphans | Documents with no links to other documents |
| Coverage and limits | How many pages were read, how many had IDs, what was ignored |
| Dependency diagram | Mermaid diagram of the top 25 documents |
| Graph data | The graph as JSON (full if small, diagram subset if large) |

**Blast radius** is the number of documents that depend on a document directly or through other documents. Arrows run from a document to the documents it depends on.

### Example (synthetic data, five documents)
```
- Highest risk: changing `FRM-MNT-221` may affect 4 documents (2 cite it directly)
- Cycles needing a human decision: 1 cycle found, for example {SOP-MNT-009, SOP-MNT-014, SOP-QA-031}
- Missing documents: 1 document referenced but not in the corpus: `SOP-MNT-999`
- Suggested order: 3 tiers. Start with tier 0 (1 document depending on no other document in the corpus)
```

## Adapt it for another client
Edit one file: `scripts/dep_utils/config.py`.

| Setting | What to change |
|---|---|
| `PREFIX_TYPES` | The document prefixes the client uses (SOP, WI, FRM, ...) and their type |
| `ACCEPT_UNLISTED_PREFIXES` | `False` for strict mode, so only listed prefixes count as documents |
| `PREFIX_STOPLIST` | Prefixes that look like IDs but are not documents (for example ISO) |
| `PAD_NUMBERS_TO` | Zero-padding width, so `SOP-MNT-14` and `SOP-MNT-014` are one document. `0` switches it off |
| `SYSTEMS` | System names to track |
| `DEPENDED_ON_BY_PHRASES`, `LINEAGE_PHRASES` | Wording that reverses a reference ("used by") or marks version history ("supersedes") |
| `CHANGE_LOG_HEADINGS`, `RELATED_HEADINGS` | Section headings to treat specially |
| `WRITE_SIDECARS` | `True` also writes `dependency_graph.json` and `dependency_graph.mmd`. Check the platform delivers them |

## Limits
- **Only references written as IDs are found.** "See the closure SOP" with no ID is not detected. The report says so.
- **Edges are only as good as the ID pattern.** The default accepts common shapes such as `SOP-MNT-014` and `WI-203`. Check the report's coverage table on the first real run and tighten `config.py` if unrelated strings are picked up.
- **Space-separated IDs** such as `SOP MNT 014` are not recognised.
- **Direction rules are phrase-based.** "Used by SOP-X" is read as SOP-X depending on this page. Other wording is read as this page depending on the target.
- **Tier order is a heuristic.** It assumes upstream documents are changed first. Reverse it if the rollout goes top-down.
- **Not yet proven on the platform:** what the aggregate step receives as its manifest (the script accepts several shapes and falls back to scanning folders), how ingestion writes page titles, and whether `tests/` inside the skill folder passes the security scan. If the scan blocks the skill, move `tests/` and this README outside the scanned folder.

## Tests
From this folder:

```
python3 -m unittest discover -s tests
```

The tests use synthetic pages in `tests/fixtures/pages/`. They run the scripts in-process, so no subprocess is started.

## Pre-flight checklist (from the BYOS batch guide)
- [x] `SKILL.md` sits at `<folder>/<skill-name>/SKILL.md`
- [x] `run_as_batch: true` in the frontmatter
- [x] `allowed-tools` includes `run_skill_script`
- [x] Both scripts are declared in `scripts/manifest.json`
- [x] Each script writes its `--output` file and exits 0
- [x] Standard library only; helper package is inside the skill folder
- [x] A quoted default output name sits near the top of each script
- [x] No helper is named `generate_*`
- [ ] Synced green on the platform
- [ ] Assigned in Project Skills
- [ ] Smoke-tested on a 3 to 5 page batch
