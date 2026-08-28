# Connections

A connection describes one database or filesystem location — either the
source you're reading from, or the target you're writing to. The same
connection can be used as a source in one job and a target in another.

## Supported types

- **PostgreSQL**, **MySQL** — host, port, database, username, and password.
- **Filesystem** — a local directory path instead of host/port. Each table
  maps to one file: `<directory>/<table>.<format>`, where format is
  Parquet, CSV, TSV, or Avro (set per connection).

## Managing connections

- **Test connection** checks that SDF can actually reach the database (or
  read/write the directory) with the credentials given.
- **Clone** duplicates a connection under a new name — handy for pointing
  a copy at a different host without retyping every field.
- **Export** / **Export all** download a connection's non-secret
  configuration as JSON — passwords are never included. **Import** reads
  that JSON back in: a connection matched by name is updated in place
  (its existing credentials are left untouched); anything new is created
  without credentials, which you then fill in by hand.
- Switch between **Cards** and **List** view with the toggle at the top of
  the page; your choice is remembered.

## Passwords

A saved password is never shown again — the field always displays a
placeholder. Leaving it as the placeholder when editing a connection keeps
the existing password; typing a new value replaces it.
