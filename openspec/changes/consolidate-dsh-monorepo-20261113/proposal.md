# Consolidate DSH repositories and synchronization

## Why

Six first-party repositories and several local synchronization jobs have become separate sources of truth. The maintainer requires one authoritative private GitHub repository and one synchronization destination: nolifeking0916/DSH.

## What Changes

- Keep DSH as the canonical repository and consolidate the other five first-party repository trees into namespaced directories.
- Preserve the existing DSH history and reviewed local commits without force-pushing.
- Make DSH the only destination for approved output, knowledge, progress-table, and context-injection synchronization.
- Reuse the existing safety gates, SHA-256 manifests, non-overlap locks, remote readback, and launchd execution model.
- Keep the three third-party forks outside the private monorepo.
- Do not automatically publish local untracked files, unresolved sensitive files, cloud placeholders, or unreviewed historical Git objects.

## Impact

- Canonical remote: private nolifeking0916/DSH.
- Existing DSH-output-hub and hr-knowledge synchronization must be reconfigured before their former repositories are archived.
- Four hr-progress-table files containing real person names remain held pending the maintainer's explicit private-to-private migration decision.
- Existing dirty DSH worktrees remain untouched until their content is audited and projected through the same safety gate.
