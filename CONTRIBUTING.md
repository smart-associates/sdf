# Contributing to Smart Data Frameworks (SDF)

Thank you for your interest in contributing to SDF.

## License

SDF is licensed under the **Business Source License 1.1 (BSL 1.1)**. Before contributing, please understand the implications:

- **You retain no ownership** of contributions — all contributions are made to the Licensed Work owned by Smart Associates Pty Ltd.
- **Contributions are subject to the BSL**, not an open source license. The work will convert to Apache 2.0 four years after each version's first public distribution.
- **Production use is permitted** provided it does not include offering SDF to third parties on a hosted or embedded basis that competes with Smart Associates Pty Ltd's commercial offerings.
- By submitting a pull request, you agree that your contribution may be incorporated into the Licensed Work under these terms.

If you are uncertain whether your intended use or contribution is permitted, contact Smart Associates Pty Ltd before proceeding.

---

## Getting Started

See [GETTING_STARTED.md](GETTING_STARTED.md) for setup instructions. For a quick start: `./start.sh dev`.

---

## Backend Conventions

- Use `async`/`await` throughout — all database access uses SQLAlchemy async sessions.
- Route handlers live in `routers/`; keep them thin and delegate to `services/`.
- Use Pydantic schemas (`schemas/`) for all request and response models.
- Passwords and credentials are encrypted at rest via `services/encryption.py`. Never store or log plaintext credentials.
- The app auto-creates tables on startup via SQLAlchemy metadata — there are no manual migration files.

### Adding a new API endpoint

1. Add the ORM model to `models/` and import it in `models/__init__.py`.
2. Add Pydantic schemas to `schemas/`.
3. Add a router in `routers/` and register it in `main.py`.
4. Put business logic in a service under `services/`.
5. Add tests in `tests/` — see the existing tests for patterns (unit, service, API).

Interactive API docs are available at [http://localhost:8000/docs](http://localhost:8000/docs) when running locally.

### Testing

Tests live in `backend/tests/` and use **pytest** with **pytest-asyncio**.

- **Unit tests** (e.g. `test_encryption.py`) — test pure functions directly, no database needed.
- **Service tests** (e.g. `test_connection_service.py`) — test service functions with a real async database session.
- **API tests** (e.g. `test_settings_api.py`) — test HTTP endpoints via `httpx.AsyncClient`.

Shared fixtures are in `conftest.py`. The test database is auto-detected the same way `start.sh` detects it: `.env` first, then `pg_isready`, then SQLite fallback.

```bash
cd backend && python -m pytest -v
```

---

## Frontend Conventions

- TypeScript throughout — avoid `any`.
- API calls live in `src/api/` and return typed responses.
- Use TanStack Query (`useQuery`, `useMutation`) for data fetching and cache invalidation.
- Components in `src/components/` should be generic and reusable; page-specific logic belongs in `src/pages/`.
- Styling is via Tailwind CSS utility classes — avoid custom CSS unless necessary.

### Testing

Tests use **Vitest** with **React Testing Library** and **MSW** for API mocking.

- **Component tests** (e.g. `StatusBadge.test.tsx`) — test rendering and props in `src/components/__tests__/`.
- **Hook tests** (e.g. `useSortableData.test.ts`) — test custom hooks in `src/hooks/__tests__/`.
- **Page tests** (e.g. `Connections.test.tsx`) — test full pages with mocked API calls in `src/pages/__tests__/`.

Shared test utilities are in `src/test/`: `test-utils.tsx` provides `renderWithProviders()` (wraps components in QueryClient + Router), and `mocks/` contains MSW handlers.

```bash
cd ui && npx vitest run
```

---

## Making Changes

### Issue tracking

Work on this repo is tracked as GitHub issues on `smart-associates/sdf`, which drives the roadmap board automatically.

- **Before starting a piece of work, open a GitHub issue for it.** A one-line title is enough (`gh issue create`).
- **Close the issue from the commit** by including `Closes #N` in the commit message. Closing the issue moves its roadmap card to Done.
- Applies to substantive work, not trivial one-off fixes — use judgement.

### Git hooks

Run this once per clone:

```bash
git config core.hooksPath .githooks
```

This enables a pre-commit hook that stamps the BSL 1.1 `Change Date` in `LICENSE`
with (commit date + 4 years) on every commit — required because each commit to
this public repo is a "publicly available distribution" of that snapshot under
the license.

### Branching

- Branch from `main`.
- Use descriptive branch names: `feat/add-mysql-support`, `fix/job-status-race`, `chore/update-deps`.

### Pull requests

- Keep PRs focused — one logical change per PR.
- Include a clear description of what the change does and why.
- If adding a new feature, update `README.md` and/or `GETTING_STARTED.md` where relevant.
- Ensure tests pass (`cd backend && python -m pytest` and `cd ui && npx vitest run`).
- Ensure the app starts cleanly (`./start.sh dev`) and the feature works end-to-end before submitting.

### Commits

- Write clear, imperative commit messages: `Add MySQL source support`, `Fix race condition in job runner`.
- Reference the tracking issue with `Closes #N` so its roadmap card moves to Done.
- Avoid committing `.env` files, secrets, or generated build artifacts.

---

## Questions

Open a GitHub issue or contact Smart Associates Pty Ltd directly.
