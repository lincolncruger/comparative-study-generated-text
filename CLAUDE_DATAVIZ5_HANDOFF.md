# Claude Code handoff: Data Visualization 5 StockNews batch

Process only the observations in `data/dataviz5_claude_evidence.json`. This is
the Claude half of a deterministic, non-overlapping split; Codex is processing
the note keys in `data/dataviz5_openai_batch_keys.json`.

Use the complete reusable prompt inside the fenced block in `Prompt 2.md`.
Substitute `StockNews API and validated linked sources` for `[SOURCE]`. Read
every article in each observation. Do not use Gemini or the OpenAI API.

Write checkpointed results to `wsj_extracted/stocknews_v2_claude.json`, keyed
by note_key. Each successful value must contain exactly:

- `summary_analysis`
- `explicit_reasons`
- `implicit_reasons`
- `categories` with all 11 keys from `Prompt 2.md`
- `sources`, with URLs copied exactly from the evidence packet

Write a separate `wsj_extracted/stocknews_v2_claude_audit.json`. For every
observation record `status`, input article count, retained and rejected sources,
and the reason for any failure. Checkpoint both files after every observation.

Do not edit `app.py`, `data/stocknews_coverage.json`,
`wsj_extracted/stocknews_v2_rebuild.json`, or the OpenAI batch-key file. Do not
publish partial results. Do not process a note key absent from the Claude packet.

Before finishing, mechanically validate the schema, source URLs, temporal
category routing, explicit/implicit attribution, the Immediate reaction
divergence rule, and the prohibition on exposing project-computed returns in
the prose. Quarantine failures rather than padding them.

