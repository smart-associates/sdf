# Settings

Application-wide configuration that applies to every connection and job.
Each setting is edited and saved independently — change a value and click
**Save** next to it.

- **CSV quoting** — how CSV files are quoted when SDF writes them: none
  (backslash-escape instead), single quotes, or double quotes.
- **CSV delimiter** — the field delimiter for CSV output; supports escape
  sequences like `\t` for tab.
- **CSV null value** — the sentinel string written for NULL fields in CSV
  output (and recognized as NULL when reading CSV back in). Leave blank for
  empty-string NULLs.
- **CSV header** — whether CSV export includes a column-header row.
- **Log level** — how much detail execution logs capture: **Minimal**
  records step outcomes only; **Detailed** also records the SQL statements
  executed along the way, which is useful when diagnosing a failure but
  produces larger logs.

Other settings appear here as plain key/value fields, with a short
description under each name explaining what it controls.
