# Processor Contract

`processor_v0` should be deterministic and explainable enough for users to
trust before any heavier server or model workflow is added.

Processor inputs should come from the SQLite local store, not by rescanning
raw JSON every time.

## v0.1 Tasks

- Normalize raw source records.
- Deduplicate by post id and URL.
- Merge related records by URL, quoted post, author, and entity tags.
- Preserve source provenance.
- Produce reviewable cards.
- Optionally translate card text.

## Local Artifacts

`scripts/plutus_wire_process.py` reads SQLite and writes:

- `review/latest-package.json`
- `review/latest-cards.json`
- `review/<run_id>.review-package.json`

`scripts/plutus_wire_tick.py --execute-adapters --process` runs the same
processor after a successful ingest tick.

The review package must contain source provenance, evidence anchors, and
check-next guidance. It must stay extractive and review-oriented; it is not a
publisher.

## Do Not Do Yet

- Do not ship Agent Plutus macro writer rules as the default public processor.
- Do not auto-publish public articles.
- Do not hide source provenance from the review UI.

## Future v1

After Agent Plutus backfill is reviewed, extract a stable public route contract
for hold, reject, split, attach, and publish behavior.
