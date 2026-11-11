---
name: process-dependency-graph
description: Deterministically maps explicit document-ID references across ingested process documents and produces an evidence-backed change-impact report.
run_as_batch: true
allowed-tools: run_skill_script read_wiki_page save_output_file
---

# Process dependency graph

## Purpose

Use this batch skill to identify the documented dependencies between procedures, work instructions, forms, policies, and configured systems. It helps a transformation lead or process analyst decide what to change first and what a proposed document change may affect.

This is a **deterministic script-mode skill**. The bundled Python scripts, not an LLM, identify references, build the graph, calculate impact, and write the report. The skill makes no model calls and must not infer relationships that are not supported by page text.

## When to use it

Run after the relevant process documents have been ingested as wiki pages and before planning a documentation or process redesign. Use a small representative batch first (three to five pages), then inspect the coverage and warnings before relying on a full-corpus result.

Do not use this report as evidence that an undocumented relationship does not exist. It maps only explicit, configured reference patterns in the available page text.

## Required input

- One or more ingested wiki pages containing process documentation.
- Prefer pages with stable document IDs such as `SOP-MNT-014`, `WI-203`, or `FRM-MNT-221`.
- Enable **Full document text on wiki** during ingestion where available. A platform-truncated page cannot reveal references after its retained text; the report flags pages near the configured truncation threshold.

Document-ID formats, normalisation, stoplisted prefixes, recognised systems, and wording rules are configured in `scripts/dep_utils/config.py`. Adapt that file for each client before production use.

## Execution contract

The platform runs the declared scripts in two stages. Each script must create the exact output path supplied by the platform and exit successfully.

1. **Per-page extraction** — `scripts/generate_dependency.py` receives one wiki page through `--input` and writes one JSON page record through `--output`.
2. **Aggregate analysis** — `scripts/generate_aggregate_dependency_graph.py` receives the batch manifest through `--manifest`, merges the page records, and writes `dependency_graph_report.md` through `--output`.

The invocation arguments for both scripts are declared in `scripts/manifest.json`. The per-page records are an implementation artifact; the aggregate Markdown report is the user-facing deliverable.

### Per-page record

The extraction record is JSON and contains the source page ID, how that ID was obtained, title, character count, truncation warning, extracted references, ignored-reference counts, lineage IDs, and parser warnings. For every retained reference it records the canonical target, document/system type, relationship direction, raw ID as written, line number, sentence context, mention count, and whether the ID was exact or normalised.

The aggregate step tolerates several manifest shapes while the Process Studio aggregate-manifest contract is being validated. It loads valid page records from the manifest; if it cannot find any, it scans the manifest and working directories for `*dependency*.json` records and adds a warning. Treat that warning as a run-validation issue, not proof of a complete corpus.

## Evidence and relationship rules

### Identifying the source page

For each page, the extractor identifies its document ID in this order: supported frontmatter field, first heading, labelled ID line (for example, `Document ID: SOP-MNT-014`), then a short first line. If no supported ID is present, the page remains in the analysis with a generated `NOID-...` identifier and a warning. It is never silently assigned a guessed business ID.

Supported frontmatter keys include `doc_id`, `docid`, `id`, `document_id`, `document_number`, `doc_number`, and `code`. Only the configured top-of-page search window is used for labelled-line and first-line fallback. This limits accidental selection of a dependency cited later in the document.

### Creating an edge

An edge is created only when the extractor finds a configured document-ID pattern or configured system name in the page text. An edge points **from the page that makes the reference to the item it depends on**:

```text
SOP-MNT-014 mentions FRM-MNT-221
SOP-MNT-014 ──depends on──> FRM-MNT-221
```

The following safeguards keep the graph conservative:

- A document name without a recognised ID is not converted into a dependency.
- ID variants are normalised only according to `config.py`; the original value and confidence are retained in the page record.
- A configured reverse phrase such as “used by SOP-X” creates `SOP-X → current page`, rather than the default direction. Reverse and lineage phrases apply when they lead directly to an ID in the same sentence (apart from simple punctuation/conjunction filler).
- Self-references do not create graph edges.
- IDs in configured change-log sections and lineage wording such as “supersedes” or “replaces” are recorded as ignored/lineage evidence, not treated as active dependencies.
- Stoplisted ID-like values are ignored.
- A cited ID that has no matching ingested page is retained as an unresolved reference; it is never invented as a document.
- System names are recognised only from the configured alias list, matched as whole words. They are captured as dependencies of the current document; reverse-phrase handling does not apply to systems.

If wording is ambiguous and does not match a configured reversal or exclusion rule, the skill uses the default reference direction. The per-page record retains the source location and context, but the user-facing report is a summary rather than a line-by-line audit trail. Review the source pages before relying on an ambiguous relationship.

### Configuration boundary

`config.py` is the policy boundary for extraction. It defines: accepted document prefixes and document types; whether unlisted uppercase prefixes are accepted; stoplisted non-document prefixes; zero-padding rules; systems and aliases; reversal and lineage phrases; change-log and related-document headings; truncation threshold; and report-size limits, including the maximum number of contextual evidence rows. The default setting accepts unlisted uppercase prefixes with at least two digits, so client production use should normally begin by reviewing that setting and tightening it to the client’s document-control standard if false positives are unacceptable.

## Analysis and output

`dependency_graph_report.md` is the authoritative output. It contains, in a decision-first order:

- **Summary:** highest-impact documents, cycles, missing documents, suggested change order, and confidence limits.
- **Most depended-on documents:** direct dependents, direct dependencies, and blast radius.
- **Change impact:** which documents cite a selected document directly.
- **Cycles:** mutually dependent document groups that need human resolution.
- **Missing documents:** referenced IDs for which no ingested page was found, with their citing pages.
- **Suggested change order:** dependency-first tiers; tier 0 documents have no in-corpus document dependencies.
- **Systems, orphans, coverage and limits:** configured system links, unconnected documents, extraction coverage, ignored references, warnings, and truncation risk.
- **Relationship evidence:** source page, line, section, captured context, mention count, and match confidence for retained graph edges; this is bounded for report usability and says when rows are omitted.
- **Dependency diagram and graph data:** a Mermaid view of the top documents plus structured graph data.

**Blast radius** is the count of distinct documents that depend on a document, directly or transitively. It is a documented-reference impact measure, not a prediction of operational, regulatory, or people impact.

### Meaning of node types and report measures

| Item | Meaning | Review action |
|---|---|---|
| Document node | An ingested page with a detected ID, or a `NOID-...` placeholder. | Confirm the source ID, especially placeholders and duplicates. |
| Unresolved node | A referenced document ID for which no ingested page was loaded. | Locate, ingest, or deliberately exclude the missing document. |
| System node | A configured application or system name found in page text. | Verify the alias is specific enough for the client environment. |
| Direct dependents | Documents that cite this item according to the edge rules. | Use as the immediate review set. |
| Direct dependencies | Items the document cites. | Use to understand its inputs or prerequisites. |
| Blast radius | All direct and indirect document dependents. | Use to prioritise review, not to approve a change automatically. |
| Cycle | A mutually reachable set of documents. | Resolve sequencing and ownership with document owners. |
| Tier | A dependency-first planning group. | Start with tier 0 only when upstream-first rollout suits the programme. |

Duplicate source-page IDs are merged into one graph node and reported as a warning. This prevents invented duplicate nodes, but it also means the report cannot distinguish two pages that claim the same business ID; correct the source documents and rerun.

## Interpretation guardrails

- Treat report findings as traceable evidence for review, not automatic change approval.
- Treat cycles, unresolved IDs, `NOID-...` nodes, normalised IDs, and truncation warnings as items requiring human verification.
- Do not claim completeness: references beyond the available wiki text, implicit references, diagrams, tables, and non-configured ID formats may be absent.
- Treat a missing-document result as “not present in this run’s loaded corpus,” not necessarily “does not exist.”
- Treat a zero blast radius as “no downstream explicit ID references were found,” not “safe to change.”
- Validate a representative sample against the source text after changing any matching or normalisation configuration.
- Do not change a process solely because its blast radius is high or low; use the report alongside document ownership, process criticality, compliance requirements, and domain review.
- If the corpus uses a different naming convention or relationship language, update `config.py`, rerun a controlled sample, and validate the findings before a full run.

## Technical constraints

- Python standard library only; no network access, subprocesses, secrets, external services, or client data bundled in this skill.
- Script outputs are deterministic for the same inputs and configuration.
- See `README.md` for setup, client adaptation, and the test command; see `schema.json` for the page-record and graph-data structures.
