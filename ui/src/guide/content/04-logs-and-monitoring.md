# Logs & monitoring

The Logs page lists every job execution, most recent first. Each row
shows the job, when it ran, its overall status, and how many of its
tables succeeded.

## Execution status

- **Running** — still in progress.
- **Succeeded** — every table completed without error.
- **Failed** — at least one table errored; the row shows how many tables
  succeeded out of the total, so a partial failure is easy to spot.

## Per-table detail

Expand an execution to see a breakdown for every table in that run:
status, record count, and duration. Expand a table further to see its
step-by-step log — reflection, DDL, and the load itself — and, if a step
failed, the exact SQL statement that was running when it errored.

## Filtering

Filter the list by job or by status. Coming from the Dashboard by
clicking a stat card or chart segment pre-applies the matching filter for
you.
