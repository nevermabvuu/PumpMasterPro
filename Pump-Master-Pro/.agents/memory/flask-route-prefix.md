---
name: Flask route prefix conflict
description: The /api/* path is proxied to the Node.js API server; Flask internal endpoints must use a different prefix.
---

In the pnpm monorepo, the artifact.toml routes `/api` (prefix) to the Node.js server on port 8080. Any Flask endpoint starting with `/api/` is intercepted by the Node.js server before reaching Flask.

**Why:** The artifact.toml has `paths = ["/api"]` for the Node.js service, which prefix-matches all `/api/*` subpaths.

**How to apply:** All Flask-internal data endpoints use `/papi/` prefix (e.g. `/papi/curve-data/<id>`, `/papi/warman-chart/<id>`, `/papi/compare-pumps`, `/papi/select-pumps`). Update JS fetch calls to match.
