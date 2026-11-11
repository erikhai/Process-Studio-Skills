---
name: dependency-probe-test
description: Probe skill. Records what a batch run gives a script (page text, IDs found, aggregate manifest shape). Test use only.
run_as_batch: true
allowed-tools: run_skill_script read_wiki_page save_output_text save_output_file write_temp_file read_temp_file
---

Probe skill for testing script-mode batch runs. The per-page script records the size, headings and document IDs of each wiki page. The aggregate script records the raw manifest it receives.
