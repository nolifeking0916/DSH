# Repository Consolidation Specification

## ADDED Requirements

### Requirement: Single authoritative destination

All enabled first-party content synchronization SHALL target the private nolifeking0916/DSH repository. No two jobs SHALL write competing projections of the same path.

#### Scenario: Approved output changes

- **WHEN** an approved output changes
- **THEN** its projection is committed and pushed only to DSH
- **AND** the remote commit and content are read back before the item is marked synced

### Requirement: Safety before publication

Every newly introduced file SHALL pass path, content, secret, personnel, size, and collision checks before entering the central commit.

#### Scenario: Person-name gate

- **WHEN** a file contains a real person name and lacks an explicit applicable approval
- **THEN** it remains outside the central commit and is reported as held

### Requirement: Non-destructive consolidation

Source snapshots SHALL be copied with SHA-256 verification and without modifying source worktrees or force-pushing canonical history.

#### Scenario: Source deletion or temporary unreadability

- **WHEN** a source file disappears or cannot be read
- **THEN** the synchronizer does not silently delete the central copy
- **AND** the condition is surfaced for review

### Requirement: Reversible synchronization cutover

Former repository writers SHALL remain unchanged until the central remote and new synchronization path have both been verified.

#### Scenario: Cutover verification fails

- **WHEN** remote readback or a synchronization probe fails
- **THEN** old writers remain in their prior state and the failure is reported
