## ISI Control Workspace

- `apps/desktop`: Electron + React operator console. Run `npm install`, `npm run dev`, or `npm run build` from this directory.
- `apps/backend`: Python control service packaged via Poetry. Use `poetry install`, `poetry run python -m isi_control.main`, or `poetry run python apps/backend/scripts/run_backend.py` for CLI.
- `configs`: Shared linter/build configuration root.
- `docs/product` & `docs/architecture`: Product documentation and system design references.
- `packages`: Placeholder for future shared libraries (TS/Python) to keep logic DRY.
- `infra`, `tools`, `tests`: Infrastructure automation, maintenance utilities, and cross-app test harnesses.
- `sample_data`: Canonical data fixtures consumed by backend analysis routines.

### Conventions

- Node workspace pinned inside `apps/desktop`; Python dependencies scoped to `apps/backend` virtualenv.
- Build artifacts live under each app (`apps/desktop/dist`, etc.) and should not be checked in.
- Electron main process launches backend through Poetry; ensure `ISI_POETRY_PATH` points to desired Poetry executable if system install differs.
