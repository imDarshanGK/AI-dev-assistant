# Security Guidelines

## Secret Detection Remediation

If a secret is detected by CI:

### 1. Revoke the Exposed Secret

Immediately disable or revoke the exposed credential.

Examples:
- API keys
- Access tokens
- Database passwords
- Cloud provider credentials

### 2. Rotate Credentials

Generate a new credential and update all dependent services.

### 3. Remove the Secret

Remove the secret from:
- Source code
- Configuration files
- Environment files accidentally committed

### 4. Clean Git History

If the secret has been committed:

- Rewrite Git history
- Remove the secret from all affected commits
- Force-push the cleaned history if appropriate

Recommended tools:

- git-filter-repo
- BFG Repo-Cleaner

### 5. Verify and Re-run CI

Confirm that:
- The secret is no longer present
- Secret scanning passes successfully
- New credentials are functioning correctly