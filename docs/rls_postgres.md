[[AI_CONFIG]]
FILE_TYPE: 'POSTGRES_RLS_POLICY_GUIDE'
INTENDED_READER: 'AI_AGENT'
PURPOSE: ['Explain Postgres RLS setup', 'Guide least-privileged DB user creation', 'Ensure secure RLS enforcement']
PRIORITY: 'HIGH'
[[/AI_CONFIG]]

# Postgres RLS guide (least-privileged setup)

This app enforces Row-Level Security (RLS) using Postgres GUCs set by `accounts.middleware.RLSSessionMiddleware`. Policies live in `db_policies/migrations/0001_rls.py` (+ fixes in 0002).

## Summary

- GUCs: `app.current_user_id`, `app.current_org_id`, `app.current_role`
- RLS tables: `orgs_organization`, `orgs_orguser`, `proposals_proposal`, `billing_subscription`
- Read: creator, explicit shares (`shared_with`), org admin; member org-read allowed
- Write: creator or org admin; subscriptions/orgusers writes require org admin

## Least-privileged DB user

Create a dedicated DB role used by the API with minimal rights:

```sql
-- Create roles
CREATE ROLE granterstellar_app LOGIN PASSWORD 'REDACTED' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE ROLE granterstellar_rw NOLOGIN;

-- Grant table privileges (future tables controlled via migrations)
GRANT USAGE ON SCHEMA public, app TO granterstellar_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO granterstellar_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO granterstellar_app;

-- Ensure RLS is active and cannot be bypassed
ALTER ROLE granterstellar_app NOBYPASSRLS;
```

Notes:

- The migrations enable RLS per table; the app role must not have BYPASSRLS.
- Avoid granting ownership or superuser; schema changes are via migrations only.
- If using multiple schemas, include them in GRANT/DEFAULT PRIVILEGES.

## Session GUCs

The middleware sets GUCs per request. For async tasks, set them at task start if hitting DB with row access logic.

```python
from django.db import connection

def set_rls(user_id: int | None, org_id: int | None, role: str = "user") -> None:
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.current_user_id', %s, false)", [str(user_id) if user_id else ""])
        cur.execute("SELECT set_config('app.current_org_id', %s, false)", [str(org_id) if org_id else ""])
        cur.execute("SELECT set_config('app.current_role', %s, false)", [role or "user"])
```

## Running RLS tests

- Tests are Postgres-only and skipped on SQLite. See:
  - `db_policies/tests/test_rls_policies.py`
  - `db_policies/tests/test_rls_matrix.py`
- Locally, point DATABASE_URL to Postgres before running tests.

### Matrix coverage (`test_rls_matrix.py`)

The matrix test exercises common CRUD + visibility paths across organizations, proposals, subscriptions, and memberships using explicit GUC setting inside each test to simulate different session contexts.

Focus areas:

- Admin vs member capability differences (writes limited to admin for org-scoped resources like subscriptions and memberships).
- Negative membership insertion path: a non-admin attempting to insert into `orgs_orguser` must raise a `ProgrammingError` under enforced policies. We intentionally keep only the negative insertion assertion to avoid introducing fragile timing / setup dependencies for a positive path that is already covered indirectly by admin-created fixtures in `setUpTestData`.
- Visibility rules for proposals: creator, shared_with list, or org admin; members restricted where appropriate.

Structure notes:

- All shared fixtures are created in `setUpTestData` (classmethod) to avoid per-test duplication and to ensure stable primary keys for policy evaluation.
- A helper sets the three GUCs (`app.current_user_id`, `app.current_org_id`, `app.current_role`) via direct SQL before each assertion block and resets after where needed.
- Tests assert denial paths using Django's transactional blocks expecting a `ProgrammingError` (Postgres RLS violation translating to blocked insert/update/delete) without relaxing policies.

When adding new RLS-governed models:

1. Extend migrations with appropriate policies first.
2. Add them to the matrix test only after confirming a minimal direct policy test (similar to `test_rls_policies.py`).
3. Prefer starting with negative (restricted) cases; add positive cases only when they increase coverage beyond existing setup-created objects.

Rationale: Emphasizing negative paths helps ensure least-privilege integrity and reduces accidental broadening of policies during refactors.

```bash
# Example (adjust as needed)
export DATABASE_URL=postgresql://USER:PASS@localhost:5432/DB
DEBUG=1 SECRET_KEY=test python manage.py test -v 2 db_policies.tests
```

## Troubleshooting

- If tests return all skipped, you’re on SQLite; set DATABASE_URL to Postgres.
- Ensure migrations ran and policies exist: `SELECT polname FROM pg_policies;`
- If an app user can see too much, verify middleware is active and GUCs set.
