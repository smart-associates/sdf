# Jobs

A job replicates a set of tables (or files) from one connection to
another. Each table can carry its own `WHERE` filter.

## Picking tables

Type a name directly (e.g. `sales.orders`), or click **Browse…** to see
the source's actual catalog: pick a schema and click **Add** on any table
or view listed, or — for a filesystem source — pick from the files in its
directory. There's no wildcard/pattern matching; every entry is one exact
table or file.

## Migration modes

- **append** — inserts rows on every run; nothing is deleted first.
- **truncate_load** — empties the target table, then loads a fresh copy.

## Auto-create target tables

When enabled, a target table that doesn't already exist yet is created
from the source's reflected schema — columns, primary key, non-PK
indexes, and (when source and target are the same kind of database) CHECK
constraints. Foreign keys are added once every table in the job has
finished loading, so it doesn't matter which order the tables are listed
in. A source's identity/auto-increment column is never recreated on the
target, since the target is about to be loaded with the source's own
values. This only ever happens the first time a table is created — an
existing target table is never altered.

## Validating and running

**Validate** checks that every source table/file actually exists (and
that the target does too, if auto-create is off) without running the job.
A bare table name that only exists in one schema, or one typed in the
wrong case, is automatically corrected against the real catalog — save
the job afterward to keep the correction. The **Validate** button is
disabled while the form has unsaved changes, since it checks the saved
job, not what's currently in the form.

**Execute** runs the job in the background; watch it on the **Logs**
page. A job that's currently running shows a live "Running" pill instead
of the normal action menu.

## Managing jobs

Each job's ⋮ menu has Execute, Edit, Clone, Export, and Delete. **Export**
/ **Export all** and **Import** work the same way as for connections — a
job's source/target are stored as name+type references, resolved against
connections that already exist on the instance you import into, never
auto-created. Switch between **Cards** and **List** view with the toggle
at the top of the page.
