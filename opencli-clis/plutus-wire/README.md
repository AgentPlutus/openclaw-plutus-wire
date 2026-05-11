# Plutus Wire OpenCLI Adapters

This directory will contain Plutus Wire adapters for OpenCLI.

Planned commands:

- `health`
- `home-tabs`
- `timeline`
- `likes`
- `bookmarks`

Adapters must use OpenCLI as an external dependency and must not copy OpenCLI
core runtime code into this repository.

Install for local development:

```bash
python3 scripts/install_opencli_adapters.py --apply
opencli validate plutus-wire
```
