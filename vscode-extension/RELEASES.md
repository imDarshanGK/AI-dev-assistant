# Release and Versioning Strategy

This document establishes the official semantic versioning rules, changelog policies, and the release process for the AI Dev Assistant project.

## 📌 Semantic Versioning (SemVer)

We strictly follow the `MAJOR.MINOR.PATCH` versioning schema:

- **MAJOR** version changes when backward-incompatible API routes or backend changes are introduced.
- **MINOR** version changes when new features or tools are added in a backward-compatible manner.
- **PATCH** version changes for backward-compatible bug fixes or UI styling refinements.

### Application to This Project:
- **Patch bump (e.g., `1.0.0` -> `1.0.1`):** Fixing an input validation bug in a FastAPI endpoint or updating CSS styling.
- **Minor bump (e.g., `1.0.0` -> `1.1.0`):** Integrating a completely new AI analysis model route into the app backend.
- **Major bump (e.g., `1.0.0` -> `2.0.0`):** Refactoring the entire core API structure, changing required request bodies, breaking previous frontend communication compatibility.

---

## 📝 Changelog Guidelines

All pull requests that alter functionality must document their changes inside `CHANGELOG.md` under the `## [Unreleased]` block using these exact categories:

- `Added` for new features (e.g., new backend features or frontend UI panels).
- `Changed` for modifications to existing tools.
- `Deprecated` for components scheduled for future removal.
- `Removed` for deleted elements.
- `Fixed` for any crash fixes, exceptions, or layout bugs.
- `Security` for fixing dependencies or code vulnerabilities.

---

## 🚀 Step-by-Step Release Process

*(Maintainer Reference Guide)*

1. **Verify State:** Confirm that the current main branch build passes all integrated local tests.
2. **Synchronize Versions:** Manually update the configuration metadata strings if applicable within core backend project files.
3. **Log the Release:** Move items grouped under `## [Unreleased]` into a freshly timestamped version block within `CHANGELOG.md`.
4. **Tag Commit and Push:** Execute the following sequence in your local shell terminal:
   ```bash
   git commit -am "chore: bump version to vX.Y.Z"
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin main --tags
