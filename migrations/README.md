# Database migrations

Fresh TempConverter databases are created from the current SQLAlchemy model.
An existing database created before 2026-08-20 may still have shorter request
metadata columns. Apply the reviewed one-time migration before accepting IPv6
client addresses or longer User-Agent values.

Back up the database first. With the local Compose stack running, stream the
SQL through the database container so the root password remains inside the
container environment:

```powershell
Get-Content -Raw `
  .\migrations\2026-08-20-expand-request-metadata.sql |
  docker compose exec --no-TTY db `
  sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'
```

Use `podman compose` instead of `docker compose` for a Podman-managed stack.
The migration only widens two `VARCHAR` columns and is safe to run again.
Long-lived production deployments should replace this manual mechanism with a
versioned migration tool and an environment-specific backup/rollback plan.
