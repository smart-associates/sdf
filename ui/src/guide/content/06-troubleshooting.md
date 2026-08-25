# Troubleshooting

## "Test connection" fails

Double-check host, port, database name, and credentials. For a
filesystem connection, make sure the directory exists and is readable
(and writable, if it's used as a target).

## A job fails partway through

Open the execution on the **Logs** page and expand the table that failed.
The step-by-step log shows which step errored and, when available, the
exact SQL statement that was running — usually enough to tell whether it
was a permissions issue, a schema mismatch, or a connectivity problem.
Tables that already succeeded are left as they are; re-running the job
only re-attempts the tables that need it according to its migration mode.

## Auto-create produced a different schema than expected

Auto-create only runs the first time a target table is created — it
never alters an existing table. If a table was already created with the
wrong shape, drop it (or fix it manually) and run the job again so
auto-create can rebuild it from the source's current schema.

## Validate reports a table as missing

The name typed for a table must resolve to exactly one table (or view) on
that connection. If the name is ambiguous (matches more than one schema)
or misspelled, use **Browse…** on the job form to pick it from the actual
catalog instead of typing it by hand.

## Import didn't bring in credentials

Exported connection and job configuration never includes passwords. After
importing, open each newly-created connection and fill in its password
before using it.
