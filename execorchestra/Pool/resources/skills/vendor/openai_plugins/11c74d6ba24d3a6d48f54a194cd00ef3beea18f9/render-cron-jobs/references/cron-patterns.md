# Cron Patterns

Common cron expressions and usage patterns for Render cron jobs.

---

## Expression Format

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, Sunday=0)
│ │ │ │ │
* * * * *
```

All times are **UTC**. Render does not support local timezones in cron expressions.

---

## Common Expressions

| Expression | Schedule |
|------------|----------|
| `* * * * *` | Every minute |
| `*/5 * * * *` | Every 5 minutes |
| `*/15 * * * *` | Every 15 minutes |
| `0 * * * *` | Every hour (at minute 0) |
| `30 * * * *` | Every hour (at minute 30) |
| `0 */2 * * *` | Every 2 hours |
| `0 0 * * *` | Daily at midnight UTC |
| `0 6 * * *` | Daily at 6:00 AM UTC |
| `0 0 * * 0` | Weekly on Sunday at midnight UTC |
| `0 0 * * 1` | Weekly on Monday at midnight UTC |
| `0 0 1 * *` | Monthly on the 1st at midnight UTC |
| `0 0 1 1 *` | Yearly on January 1st at midnight UTC |
| `0 6 * * 1-5` | Weekdays at 6:00 AM UTC |
| `0 0,12 * * *` | Twice daily (midnight and noon UTC) |

---

## Framework-Specific Examples

### Python

```yaml
- type: cron
  name: cleanup
  runtime: python
  schedule: "0 0 * * *"
  buildCommand: pip install -r requirements.txt
  startCommand: python scripts/cleanup.py
```

### Node.js

```yaml
- type: cron
  name: report-generator
  runtime: node
  schedule: "0 6 * * 1"
  buildCommand: npm ci
  startCommand: node scripts/weekly-report.js
```

### Bash / Shell

```yaml
- type: cron
  name: sync-data
  runtime: python
  schedule: "*/30 * * * *"
  buildCommand: "true"
  startCommand: /bin/bash scripts/sync.sh
```

### Ruby

```yaml
- type: cron
  name: daily-task
  runtime: ruby
  schedule: "0 0 * * *"
  buildCommand: bundle install
  startCommand: bundle exec ruby scripts/task.rb
```

---

## Error Handling

- **Exit codes**: exit 0 for success, non-zero for failure. Render marks the run as failed on non-zero exit.
- **Logging**: write to stdout/stderr. Render captures output in service logs.
- **Retries**: Render does not auto-retry failed cron runs. Implement retry logic in your script if needed.
- **Timeouts**: if your job risks approaching the 12-hour limit, add a timeout in your script.

---

## Environment Variables

Cron jobs support the same env var patterns as other services:

```yaml
envVars:
  - key: DATABASE_URL
    fromDatabase:
      name: my-db
      property: connectionString
  - key: API_KEY
    sync: false
```
