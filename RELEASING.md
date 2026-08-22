# Releasing rustfava

This document describes the release process for rustfava.

## Overview

A release involves:

1. Creating a git tag
1. Automated builds (desktop apps, PyPI, Docker)
1. Publishing the release
1. Updating Nix flake sources

## Step-by-Step Process

### 1. Create and push a version tag

```bash
git checkout main
git pull
git tag v0.1.x
git push origin v0.1.x
```

### 2. Wait for CI workflows

The tag triggers several workflows:

| Workflow              | Purpose                                    | Duration |
| --------------------- | ------------------------------------------ | -------- |
| `desktop-release.yml` | Builds desktop apps for all platforms      | ~10 min  |
| `build-publish.yml`   | Builds and publishes to PyPI, Docker, COPR | ~60 min  |

Monitor at: https://github.com/rustledger/rustfava/actions

### 3. PyPI deployment

The workflow is `publish.yml` (this document previously called it
`build-publish.yml`, which does not exist).

Its `publish` job targets the **`pypi` environment, which has protection rules**
— the run sits in `waiting` until a deployment reviewer approves it. Approve at
the run's page, or:

```bash
gh api repos/rustledger/rustfava/actions/runs/<run-id>/pending_deployments \
  -f state=approved -f "environment_ids[]=<id>" -f comment=""
```

Everything before it (`build`, `docker`, `smoke-wheel`) runs unattended, so the
Docker image publishes without approval — only PyPI waits.

### 4. Publish the GitHub release

Once `desktop-release.yml` completes, it creates a **draft release** with:

- `.AppImage` (Linux)
- `.deb`, `.rpm` (Linux packages)
- `.dmg` (macOS)
- `.msi`, `.exe` (Windows)
- `.tar.gz` (Linux tarball for Nix)

Publish it:

```bash
gh release edit v0.1.x --draft=false
```

Or via GitHub UI: https://github.com/rustledger/rustfava/releases

### 5. Update Nix flake sources

The `update-flake-sources.yml` workflow fires when a tag-triggered
`Desktop Release` run completes (it can also be run manually via
`gh workflow run update-flake-sources.yml -f version=vX.Y.Z`). It:

1. Downloads release tarballs
1. Computes SRI hashes
1. Creates a PR updating `desktop-sources.json`

Merge the PR when it passes CI.

### 6. Verify

Test the release:

```bash
# Desktop app via Nix
nix run github:rustledger/rustfava#desktop --refresh

# CLI via Nix
nix run github:rustledger/rustfava --refresh

# CLI via PyPI
uv tool install rustfava --upgrade

# Docker
# NB: the image tag has no "v" prefix
docker pull ghcr.io/rustledger/rustfava:0.1.x
```

## Release Artifacts

| Artifact       | Source                               | Distribution    |
| -------------- | ------------------------------------ | --------------- |
| Desktop apps   | `desktop-release.yml`                | GitHub Releases |
| Python package | `build-publish.yml`                  | PyPI            |
| Docker image   | `build-publish.yml`                  | GHCR            |
| Nix flake      | `flake.nix` + `desktop-sources.json` | GitHub          |

## Troubleshooting

### Draft release not created

Check that `desktop-release.yml` completed successfully. The release job only
runs on tags.

### Nix flake sources not updated

The `update-flake-sources.yml` workflow triggers when the tag's
`Desktop Release` run completes successfully. If it didn't fire, dispatch it
manually: `gh workflow run update-flake-sources.yml -f version=vX.Y.Z`.

### PyPI publish failed

Check the workflow logs. Common issues:

- Version already exists on PyPI (can't overwrite)
- Missing approval for the `pypi` environment
