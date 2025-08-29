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

```bash
# Example (adjust as needed)
export DATABASE_URL=postgresql://USER:PASS@localhost:5432/DB
DEBUG=1 SECRET_KEY=test python manage.py test -v 2 db_policies.tests
```

## Troubleshooting
- If tests return all skipped, you’re on SQLite; set DATABASE_URL to Postgres.
- Ensure migrations ran and policies exist: `SELECT polname FROM pg_policies;`
- If an app user can see too much, verify middleware is active and GUCs set.
