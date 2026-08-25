# Getting started

SDF (Smart Data Frameworks) moves data between databases and files. The
workflow has three steps:

1. **Connections** — register the databases and filesystem locations you
   want to move data between.
2. **Jobs** — pick a source connection, a target connection, and the
   tables (or files) to replicate.
3. **Logs** — run the job and watch it execute, table by table.

## The Dashboard

The Dashboard is the home page. It shows recent execution activity, a
records-migrated chart, and your registered connections and jobs at a
glance. Clicking a stat card or chart segment takes you to the Logs page,
pre-filtered to match what you clicked.

## A minimal first job

1. Go to **Connections** and add your source and target databases (or a
   filesystem location).
2. Go to **Jobs**, click **New Job**, pick the source and target
   connections you just created.
3. Add the tables to replicate — either type a name directly, or click
   **Browse…** to pick from the source's actual schemas and tables.
4. Choose a migration mode (**append** or **truncate_load**), and enable
   **Auto-create target tables** if the tables don't exist on the target
   yet.
5. Click **Validate** to check the job before running it, then **Execute**.
6. Watch progress on the **Logs** page — each execution expands to show
   per-table status, record counts, and step-by-step logs.

See the **Connections** and **Jobs** sections for the details on each type
of source/target and what auto-create actually does to the schema.
