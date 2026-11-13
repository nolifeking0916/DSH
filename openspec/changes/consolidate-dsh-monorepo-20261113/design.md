# Design

## Context

The canonical integration branch is consolidate/monorepo-20261113, based on DSH origin/main at 6344ed501ac0a1e4d804e86377554d8b7a46a602. Integration occurs in an independent clean clone, not in either dirty daily-use worktree.

## Goals / Non-Goals

### Goals

- One private authoritative repository and one synchronization destination.
- Byte-for-byte source snapshots with source OIDs and collision detection.
- Safety review before the first central commit and before every later sync.
- Remote commit/tree/blob verification and reversible cutover.

### Non-Goals

- Importing third-party forks into the private monorepo.
- Rewriting or force-pushing DSH history.
- Automatically deleting source files or remote history.
- Making private personnel data public or sending it to OpenViking.

## Decisions

1. Preserve the DSH root as the primary tree.
2. Place hr-knowledge at hr-knowledge/, dsh-context-injection at packages/dsh-context-injection/, hr-progress-table at apps/hr-progress-table/, and hr-data-center at apps/hr-data-center/.
3. Promote DSH-output-hub's dsh-workspace/ and manifests/ projections to the root; keep its own documentation under packages/dsh-output-hub/. Skip its duplicate hr-knowledge projection.
4. Use exact source commit OIDs and SHA-256 manifests. Source deletion does not delete the central copy.
5. Reuse the existing sync_online.py Git-only executor pattern with separate profiles, but point every enabled profile at DSH.
6. Keep 60-second polling and 300-second launchd fallback only after the first central remote verification succeeds.
7. Archive old first-party remotes only after cutover stability is demonstrated; never archive before the central content and running jobs are verified.

## Risks / Trade-offs

- Four hr-progress-table files are blocked by the person-name gate; excluding them leaves that application incomplete.
- Local DSH commits and dirty worktrees may conflict with origin/main or contain sensitive material; they require independent review.
- A monorepo increases checkout size but removes cross-repository drift.

## Migration Plan

1. Freeze source OIDs and generate the safety-reviewed projection.
2. Integrate reviewed local DSH commits without rewriting their history.
3. Run tests, validate OpenSpec, and scan the final central tree.
4. Push the integration branch, verify it remotely, then fast-forward main through a reviewed update.
5. Cut over synchronization jobs and verify new commits on DSH.
6. Stop old-repository writers and archive old remotes after the stability window.

## Open Questions

- Whether the four already-private hr-progress-table files may be copied into the equally private DSH repository without redaction.
- Which untracked local files are canonical outputs versus disposable state.
