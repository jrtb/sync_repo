# Legacy Utilities and Documentation

This project now prioritizes the full‑screen TUI workflow (`scripts/sync.py`) backed by the refactored core engine (`core/`). The items listed here are considered legacy/utility components. They are kept for compatibility, education, and tests, but are no longer the primary interface.

## Scripts (kept for compatibility)

- `scripts/setup.py`: Environment and project scaffolding helpers
- `scripts/setup-iam-user.py`: Example IAM user setup (educational; use your own org processes in production)
- `scripts/setup-credentials.py`: Example credential wiring via AWS CLI profiles
- `scripts/validate.py`: Configuration and environment validation routines
- `scripts/test-credentials.py`: Basic AWS CLI credential checks
- `scripts/verify-production-setup.py`: Lightweight production readiness checks
- `scripts/storage-class-manager.py`: Storage class analysis and basic cost hints
- `scripts/retry_failed_uploads.py`: Retry helper for failed uploads
- `scripts/backup.py`, `scripts/restore.py`: Simple config/log/data backup and restore helpers
- `scripts/cleanup.py`: Cleanup of temp files, logs, and old backups
- `scripts/security_manager.py`, `scripts/security-audit.py`, `scripts/policy_validator.py`: Security examples and validation helpers
- `scripts/monitor.py`, `scripts/report.py`: Monitoring/reporting examples
- `scripts/enable_versioning.py`: Bucket versioning helper
- `scripts/verify_aws_pricing.py`, `scripts/test_pricing.py`: Pricing verification examples
- `scripts/clean-git-history.py`: One‑time repo maintenance helper
- `scripts/debug_sync_issue.py`: Diagnostics helper

These utilities remain in place to support existing tests and workflows. Prefer the TUI for day‑to‑day sync operations.

## Documentation (legacy/educational)

The following documents are retained for completeness and AWS learning. They are not strictly required to use the TUI:

- `docs/aws-setup.md`, `docs/aws-cli-installation.md`, `docs/iam-user-setup.md`
- `docs/storage-class-management.md`, `docs/monitoring-and-reporting.md`
- `docs/security.md`, `docs/security-audit-summary.md`
- `docs/path-consistency-testing.md`, `docs/versioning-implementation-summary.md`
- `docs/documentation-style-guide.md`, `workflow.md`

## Recommended path

- Use `s3-sync` (via `./install-path-alias.sh`) or `python scripts/sync.py` to run the full‑screen TUI.
- Keep using the utilities only when needed (e.g., validation, backups) or when working through the educational material.


