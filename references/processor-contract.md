# Processor Contract

`processor_v0` should be deterministic and explainable enough for users to
trust before any heavier server or model workflow is added.

## v0.1 Tasks

- Normalize raw source records.
- Deduplicate by post id and URL.
- Merge related records by URL, quoted post, author, and entity tags.
- Preserve source provenance.
- Produce reviewable cards.
- Optionally translate card text.

## Do Not Do Yet

- Do not ship Agent Plutus macro writer rules as the default public processor.
- Do not auto-publish public articles.
- Do not hide source provenance from the review UI.

## Future v1

After Agent Plutus backfill is reviewed, extract a stable public route contract
for hold, reject, split, attach, and publish behavior.
