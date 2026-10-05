# voitta-mcp

Small, single-purpose MCP servers from Voitta. Each server lives in its own
top-level directory with its own `pyproject.toml` and README describing how to
start it.

| Server | Description |
|---|---|
| [`crm-highlevel/`](crm-highlevel/README.md) | Read-only HighLevel CRM (contacts, deals, notes, pipelines) |

## CI and releases

- `checks` runs on every PR and push to `master`: each server (a top-level
  directory with `pyproject.toml` and `Dockerfile`) must compile and its image
  must build.
- `release` runs on push to `master`. For each server whose `pyproject.toml`
  version has no `<server>-v<version>` tag yet, it pushes the image to
  `ghcr.io/voitta-ai/voitta-mcp/<server>:<version>` and `:latest`
  (linux/amd64 and linux/arm64), then creates the tag and a GitHub release
  with notes generated from merged PRs since that server's previous release.

Feature PRs leave the version alone. To cut a release, merge a PR that only
bumps the server's `version` in its `pyproject.toml`.
