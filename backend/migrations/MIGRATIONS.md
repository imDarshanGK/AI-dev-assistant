# Database Migrations

This project uses [Alembic](https://alembic.sqlalchemy.org/) with SQLAlchemy for database schema migrations.

## Setup

```bash
cd backend
pip install alembic sqlalchemy
```

## Running Migrations

### Upgrade to latest
```bash
alembic upgrade head
```

### Downgrade one step
```bash
alembic downgrade -1
```

### Check current version
```bash
alembic current
```

### View migration history
```bash
alembic history
```

## Creating a New Migration

```bash
alembic revision -m "describe your change here"
```

Then edit the generated file in `migrations/versions/` and fill in `upgrade()` and `downgrade()`.

## Migration Files

| File | Description |
|------|-------------|
| `0001_initial_schema.py` | Creates all base tables: users, query_history, favorite_results, digest_subscriptions, shares, audit_logs |
| `0002_add_user_profile_fields.py` | Adds full_name, avatar_url, bio, updated_at to users table |
| `0003_add_analysis_token_count.py` | Adds token_count, is_public, view_count to query_history table |

## Environment Variable

Set `DATABASE_URL` to override the default SQLite URL:

```bash
export DATABASE_URL=postgresql://user:password@localhost/dbname
```
