# Tooling regression loop analysis

## Context

Recent merges show a repetitive cadence of "fix imports", "repair lint", and "restore test discovery" commits landing minutes apart. The cycle began when the Telegram integration was developed inside a new `backend/` workspace that shadowed the existing root `app/` package and introduced a second tooling stack managed by Poetry. Downstream work and CI continued to run from the monorepo root with pip and `requirements.txt`, so every change toggled between two conflicting sources of truth for imports, dependency versions, and static analysis settings. The history below catalogues the loop so we can anchor remediation on evidence rather than intuition.

## Timeline of the regression loop

### Phase 1 – Telegram feature shipped into the duplicate backend workspace (`db48445` → `9462e48`)

- `db48445` added the Telegram client under `backend/app/...` with its own `backend/pyproject.toml`, creating a second `app` package on `PYTHONPATH` whenever tests were run from the repo root.
- Because the Poetry environment carried different dependency pins than the pip workflow, follow-up commits (`5fdc632`, `7fe4e4b`) thrash the `httpx` version to satisfy Poetry while `requirements.txt` lagged behind; `3297dc8` later had to copy the new `python-telegram-bot` dependency into the root `requirements.txt` to unblock CI.
- Import resolution immediately became unstable. `bfe9ef4` moved modules into `app.integrations` to dodge circular imports, `8a44e29` patched `__init__.py` so the package was visible, and `af6398d`/`deb24f8` rewired tests to tolerate a missing Telegram dependency.
- Test discovery vacillated between adding and removing `sys.path` hacks (`9462e48`, `93dba56`) because pytest executed against whichever `app` package happened to be ahead on the module search path.

### Phase 2 – Validator, mypy, and packaging churn inside `backend/` (`653c6e1` → `96ecd3a`)

- The backend workspace used Poetry defaults (Pydantic v2) while the root runtime was still pinned to `pydantic[email]==1.10.12`. Commits `653c6e1` and `63f3424` bounce between `root_validator` and `model_validator`, illustrating the version mismatch.
- Type-checking and imports continued to break in alternating environments: `cc000ce` patched mypy configuration, `1f6ac03` reintroduced exports in `backend/app/__init__.py`, while `bdf23f0` renamed the package to `backend_app` in an attempt to disambiguate imports—only for `81cc0e4` to undo it hours later because consumers still expected `app`.
- Every rename forced more Ruff import order fixes (`93dba56`, `1f6ac03`, `da4176f`) because the two toolchains contained disjoint lint settings. Ruff ran with Poetry’s config under `backend/pyproject.toml`, but root developers relied on ad-hoc defaults.

### Phase 3 – Deleting the duplicate workspace but inheriting its debt (`9e5aae2` → `552587b`)

- `9e5aae2` finally removed `/backend`, updated CI workflows, and declared the root `app/` package canonical. The change was sweeping but landed on `main` before the test suite was stabilized.
- With the backend folder gone, root tests that previously leaned on Poetry’s `pythonpath = ["app"]` started failing again. The response was another round of emergency patches: `a6c79f2` tweaked Ruff config, `8043d68` reformatted large swaths of the tree, `f8795f3` rewired Celery retry handling, and `552587b` reintroduced manual `sys.path` manipulation in `tests/conftest.py` so pytest could find `app`.
- The repo now had a single code location, but it still carried the divergent tooling defaults (Ruff, Black, mypy) and a lingering mix of Poetry- vs pip-oriented instructions in docs and CI.

### Phase 4 – Consolidating tooling at the root (`a684f28` → `6622e6e` → `c9fa970`)

- Documentation (`a684f28`) captured the decision to adopt the root `app/` as the only backend package and pointed developers at a unified workflow.
- `6622e6e` (and the merge-up `c9fa970`) rewired GitHub Actions and pre-commit to install both `requirements*.txt`, dropped the Poetry workflows, and moved all lint/type/test settings into the single root `pyproject.toml`. That commit also deleted the remaining `sys.path` hacks from `tests/conftest.py`, proving the configuration debt had been the blocker all along.

## Symptom clusters and representative commits

### Import and module resolution failures

- `bfe9ef4`, `8a44e29`, `af6398d`, `deb24f8`, `9462e48`, `93dba56`, `da4176f`, `1520993`, and `552587b` all adjust import locations or mutate `sys.path` to placate pytest. Each fix targeted the environment currently failing (Poetry vs pip), reintroducing breakage for the other.
- `bdf23f0` → `81cc0e4` demonstrates the whiplash caused by two packages named `app`: renaming to `backend_app` briefly quieted conflicts, but consumer code and tests bound to `app` immediately failed, forcing a revert and more aliasing logic in `backend/app/__init__.py` (`7530516`, `96ecd3a`).

### Dependency and version drift

- `5fdc632` and `7fe4e4b` pendulum between `httpx` 0.26.x and 0.25.x as Poetry and pip resolved constraints differently.
- `3297dc8` surfaced that new dependencies were only recorded in the deleted workspace; without parity in `requirements.txt` CI could not even import the Telegram client.
- The Pydantic validator tug of war (`653c6e1`, `63f3424`, `02ba81e`) is a direct artifact of Poetry permitting Pydantic v2 APIs while the production/runtime environment kept v1 pinned.

### Lint, formatting, and test harness thrash

- Ruff import-order and Black formatting fixes appear in nearly every commit in the sequence (`e7803dc`, `93dba56`, `1f6ac03`, `8043d68`). The duplication of configuration files (`backend/pyproject.toml` vs the late-arriving root `pyproject.toml`) meant developers could not rely on a single set of rules.
- Test harness logic shifted repeatedly: `9462e48`, `93dba56`, `da4176f`, `02ba81e`, `1520993`, `7efe638`, and `552587b` alternated between adding and deleting `sys.path` munging, patching fixtures, or re-exporting modules, underscoring how fragile discovery became once two toolchains diverged.

## Root cause analysis

1. **Duplicate backend packages created competing import targets.** Shipping the Telegram feature inside `backend/app` (`db48445`) while the legacy code lived in the root `app/` meant Python’s import search path returned whichever package appeared first. Running tests or Ruff from `/backend` vs `/` yielded different modules, spawning circular imports (`bfe9ef4`) and repeated attempts to alias models (`7530516`, `96ecd3a`).
2. **Tooling and dependency definitions drifted across workspaces.** The Poetry file under `/backend` carried its own dependency graph and tool configuration. Root-level workflows continued to rely on `requirements.txt` and ad-hoc settings. That split produced:
   - Version conflicts (httpx, python-telegram-bot) and Pydantic API mismatches (`653c6e1`).
   - Linter disagreement and repeated reformatting because Ruff/Black/Mypy read different configs depending on the directory.
   - pytest behaving differently: Poetry injected `pythonpath = ["app"]`, while the root setup did not, forcing brittle `sys.path` edits (`552587b`).
3. **Fixes landed directly on `main` without a stabilization window.** Each patch addressed the symptom currently breaking CI but reintroduced the failure class that a previous commit had papered over. Because both toolchains co-existed, the team had no reproducible way to verify fixes across all environments before merging.

## Remediation strategy

The clean-up currently in flight (removal of `/backend`, unified docs, new `pyproject.toml`) aligns with the following strategy. Remaining tickets should focus on making each step airtight so we do not regress:

1. **Enforce a single backend package.** Keep all server code under `app/` and delete fallbacks, aliases, or deprecated `backend_*` directories. Guard against regressions with CI that fails if a second `app` package is introduced.
2. **Centralize tooling configuration.** Maintain Ruff, Black, mypy, and pytest settings solely in the root `pyproject.toml`. Remove legacy configs from documentation and scripts so developers cannot accidentally invoke the old stack.
3. **Pin dependencies once.** Treat `requirements.txt` + `requirements-dev.txt` as the source of truth. Any new runtime or tooling dependency must be added there first, then reflected in Docker and CI images to keep environments in lockstep.
4. **Keep pytest path hygiene simple.** Rely on `pyproject.toml`’s `pythonpath = ["."]` and remove remaining `sys.path` manipulations once all packages live under `app/`. Future feature branches should validate that tests run without directory-specific hacks.
5. **Document and automate the guardrails.** Extend the onboarding docs (`a684f28`) with a checklist for adding third-party packages and updating tooling configs. Add CI checks (pre-commit, workflows) that assert only the canonical configs are edited.

Following this plan will convert the patch-and-revert loop into a stable foundation. The team can then iterate on the Telegram feature (and future integrations) without reopening the same import, lint, and test-discovery wounds.
