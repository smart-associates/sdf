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

Interactive API docs are available at [http://localhost:8000/docs](http://localhost:8000/docs) when running locally.

---

## Frontend Conventions

- TypeScript throughout — avoid `any`.
- API calls live in `src/api/` and return typed responses.
- Use TanStack Query (`useQuery`, `useMutation`) for data fetching and cache invalidation.
- Components in `src/components/` should be generic and reusable; page-specific logic belongs in `src/pages/`.
- Styling is via Tailwind CSS utility classes — avoid custom CSS unless necessary.

---

## Making Changes

### Branching

- Branch from `main`.
- Use descriptive branch names: `feat/add-mysql-support`, `fix/job-status-race`, `chore/update-deps`.

### Pull requests

- Keep PRs focused — one logical change per PR.
- Include a clear description of what the change does and why.
- If adding a new feature, update `README.md` and/or `GETTING_STARTED.md` where relevant.
- Ensure the app starts cleanly (`./start.sh dev`) and the feature works end-to-end before submitting.

### Commits

- Write clear, imperative commit messages: `Add MySQL source support`, `Fix race condition in job runner`.
- Avoid committing `.env` files, secrets, or generated build artifacts.

---

## Questions

Open a GitHub issue or contact Smart Associates Pty Ltd directly.
