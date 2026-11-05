# Queue framework setup on Render

Minimal patterns for running each stack as a **`type: worker`** service. Replace regions, plans, and commands to match your repo.

**Shared Key Value (Redis-style) wiring** — add once, reference from every consumer that needs the broker:

```yaml
services:
  - type: keyvalue
    name: jobs
    region: oregon
    plan: starter
    ipAllowList: []
```

**Env var** (worker or web that enqueues):

```yaml
envVars:
  - key: REDIS_URL
    fromService:
      name: jobs
      type: keyvalue
      property: connectionString
```

Set Key Value **maxmemory policy** to **`noeviction`** in the Dashboard so queue keys are never evicted like cache entries.

---

## Celery (Python)

**Install**

```bash
pip install "celery[redis]"
```

**Minimal app** (`tasks.py` / package root):

```python
import os
from celery import Celery

app = Celery("tasks", broker=os.environ["REDIS_URL"])

@app.task
def add(x, y):
    return x + y
```

**Start command** (adjust module path):

```bash
celery -A tasks worker --loglevel=info
```

**Blueprint (worker)**

```yaml
  - type: worker
    name: celery-worker
    runtime: python
    region: oregon
    plan: starter
    buildCommand: pip install -r requirements.txt
    startCommand: celery -A tasks worker --loglevel=info
    envVars:
      - key: REDIS_URL
        fromService:
          name: jobs
          type: keyvalue
          property: connectionString
```

---

## Sidekiq (Ruby)

**Gemfile**

```ruby
gem "sidekiq"
```

**Initializer** (`config/initializers/sidekiq.rb` or equivalent):

```ruby
Sidekiq.configure_server do |config|
  config.redis = { url: ENV.fetch("REDIS_URL") }
end

Sidekiq.configure_client do |config|
  config.redis = { url: ENV.fetch("REDIS_URL") }
end
```

**Start command**

```bash
bundle exec sidekiq
```

**Blueprint (worker)**

```yaml
  - type: worker
    name: sidekiq
    runtime: ruby
    region: oregon
    plan: starter
    buildCommand: bundle install
    startCommand: bundle exec sidekiq
    envVars:
      - key: REDIS_URL
        fromService:
          name: jobs
          type: keyvalue
          property: connectionString
```

---

## BullMQ (Node.js)

**Install**

```bash
npm install bullmq ioredis
```

**Minimal worker** (`worker.js`):

```javascript
const { Worker } = require("bullmq");
const IORedis = require("ioredis");

const connection = new IORedis(process.env.REDIS_URL, {
  maxRetriesPerRequest: null,
});

const worker = new Worker("myqueue", async (job) => job.data, { connection });
```

**Start command**

```bash
node worker.js
```

**Blueprint (worker)**

```yaml
  - type: worker
    name: bullmq-worker
    runtime: node
    region: oregon
    plan: starter
    buildCommand: npm ci
    startCommand: node worker.js
    envVars:
      - key: REDIS_URL
        fromService:
          name: jobs
          type: keyvalue
          property: connectionString
```

---

## Asynq (Go)

**Module**

```bash
go get github.com/hibiken/asynq
```

**Minimal worker** (simplified):

```go
package main

import (
    "log"
    "os"

    "github.com/hibiken/asynq"
)

func main() {
    redisOpt, err := asynq.ParseRedisURI(os.Getenv("REDIS_URL"))
    if err != nil {
        log.Fatal(err)
    }
    srv := asynq.NewServer(redisOpt, asynq.Config{Concurrency: 10})
    mux := asynq.NewServeMux()
    // mux.HandleFunc("task:type", handler)
    if err := srv.Run(mux); err != nil {
        log.Fatal(err)
    }
}
```

**Start command** (after `go build` in `buildCommand` or run `go run`):

```bash
./worker
```

**Blueprint (worker)**

```yaml
  - type: worker
    name: asynq-worker
    runtime: go
    region: oregon
    plan: starter
    buildCommand: go build -o worker ./cmd/worker
    startCommand: ./worker
    envVars:
      - key: REDIS_URL
        fromService:
          name: jobs
          type: keyvalue
          property: connectionString
```

---

## Oban (Elixir)

Oban uses **PostgreSQL** as its queue store—**not** Redis. Provision a Render **PostgreSQL** database and wire **`DATABASE_URL`**.

**Config** (`config/runtime.exs` or `config/prod.exs` pattern):

```elixir
config :my_app, Oban,
  repo: MyApp.Repo,
  queues: [default: 10]
```

**Start command** (typical Release):

```bash
_build/prod/rel/my_app/bin/my_app start
```

**Blueprint (worker)** — `fromDatabase` for `DATABASE_URL`:

```yaml
databases:
  - name: app-db
    plan: basic-256mb
    region: oregon

services:
  - type: worker
    name: oban-worker
    runtime: elixir
    region: oregon
    plan: starter
    buildCommand: mix deps.get && mix release
    startCommand: _build/prod/rel/my_app/bin/my_app start
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: app-db
          property: connectionString
```

Do **not** point Oban at Key Value unless you are using an **experimental or custom** backend; default Oban is **Postgres-only**.
