# OpenCLI Browser Bridge

Plutus Wire depends on OpenCLI for browser automation and logged-in page access.

## Dependency

Install OpenCLI separately:

```bash
npm install -g @jackwener/opencli
```

Plutus Wire is not an OpenCLI fork. If a change is needed in OpenCLI core,
prefer an upstream issue or pull request.

## Adapter Boundary

Plutus Wire owns adapters under:

```text
opencli-clis/plutus-wire/
```

OpenCLI owns:

- browser bridge runtime
- daemon lifecycle
- adapter registration system
- browser page primitives

## Version Reporting

Every run manifest should include:

- `opencli_path`
- `opencli_version`
- `adapter_version`
- `source_config_hash`
