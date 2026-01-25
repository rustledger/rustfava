# Syncing with Upstream Fava

rustfava is a fork of [Fava](https://github.com/beancount/fava) that replaces the beancount parser with [rustledger](https://github.com/rustledger/rustledger). This document describes how to sync relevant changes from upstream.

## Background

The fork diverges significantly from upstream in the backend:

| Component | Fava | rustfava |
|-----------|------|----------|
| Parser | Python beancount | rustledger (WASM) |
| Core modules | `fava/core/`, `fava/beans/` | `rustfava/rustledger/` |
| Package manager | npm | bun |

The frontend is largely unchanged and can usually accept upstream patches.

## Checking for Upstream Changes

```bash
# Fetch upstream
git fetch upstream

# Find the common ancestor (fork point)
git merge-base main upstream/main

# Count commits since fork
git rev-list --count $(git merge-base main upstream/main)..upstream/main

# List upstream commits since fork
git log --oneline $(git merge-base main upstream/main)..upstream/main
```

## Categorizing Commits

Review each upstream commit and categorize:

### Safe to cherry-pick

- **Frontend changes** (`frontend/src/`) - UI, routing, components
- **Documentation** (`docs/`, `*.md`)
- **Templates** (`src/fava/templates/`)
- **Static assets** (`src/fava/static/`)
- **Extension API** (if not touching core)

### Requires review

- **Tests** - may reference beancount-specific behavior
- **API endpoints** - check if they depend on beancount types

### Cannot cherry-pick

- **Core modules** - `src/fava/core/`, `src/fava/beans/`
- **Beancount imports** - anything importing from `beancount.*`
- **Inventory/position logic** - replaced by rustledger

## Cherry-Pick Workflow

```bash
# 1. Create a sync branch
git checkout main
git pull origin main
git checkout -b sync/upstream-YYYY-MM

# 2. Cherry-pick safe commits (oldest first)
git cherry-pick <commit-hash>

# 3. If conflicts occur, resolve them:
#    - For package-lock.json conflicts: git rm frontend/package-lock.json
#    - For renamed files (fava -> rustfava): update paths
#    - For deleted files: skip the commit with git cherry-pick --skip

# 4. Update lockfile if package.json changed
nix develop --command bash -c "cd frontend && bun install"
git add frontend/bun.lock
git commit -m "chore: update bun.lock for upstream sync"

# 5. Test the build
nix develop --command bash -c "cd frontend && bun run build"
nix develop --command bash -c "just test"

# 6. Push and create PR
git push -u origin sync/upstream-YYYY-MM
gh pr create --title "chore: sync upstream fava changes (Month YYYY)"
```

## Common Conflicts

### package-lock.json

rustfava uses bun instead of npm. Remove the conflicting file:

```bash
git rm frontend/package-lock.json
git cherry-pick --continue
```

### File renames (fava -> rustfava)

Upstream references `src/fava/` but rustfava uses `src/rustfava/`. The cherry-pick usually handles this via directory mapping, but manual fixes may be needed.

### Deleted core files

If upstream modifies files that rustfava deleted (like `core/inventory.py`), skip the commit:

```bash
git cherry-pick --skip
```

## After Syncing

1. **Run the test suite**: `just test`
2. **Build the frontend**: `just frontend`
3. **Manual testing**: Start the app and verify functionality
4. **Update this doc**: Note the last sync date and any new patterns

## Sync History

| Date | PR | Commits | Notes |
|------|-----|---------|-------|
| 2026-01-25 | #22 | 2 | Extension types, router improvements |

## Upstream Monitoring

Consider setting up notifications for upstream releases:

1. Watch the [beancount/fava](https://github.com/beancount/fava) repository
2. Review the [Fava changelog](https://github.com/beancount/fava/blob/main/CHANGELOG.md) periodically
3. Sync quarterly or when significant features are added
