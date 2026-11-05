# Key Value Connection Examples

All examples use the internal URL via the `REDIS_URL` environment variable. Wire `REDIS_URL` in your Blueprint with `fromService`:

```yaml
envVars:
  - key: REDIS_URL
    fromService:
      name: cache
      type: keyvalue
      property: connectionString
```

## Node.js (ioredis)

```javascript
import Redis from 'ioredis'

const redis = new Redis(process.env.REDIS_URL)

await redis.set('key', 'value')
const result = await redis.get('key')
console.log(result)
```

## Node.js (node-redis)

```javascript
import { createClient } from 'redis'

const client = createClient({ url: process.env.REDIS_URL })
await client.connect()

await client.set('key', 'value')
const value = await client.get('key')
console.log(value)
```

## Python (redis-py)

```python
import os
import redis

r = redis.from_url(os.environ['REDIS_URL'])

r.set('key', 'value')
print(r.get('key').decode())
```

## Python (Celery)

```python
import os
from celery import Celery

app = Celery('tasks', broker=os.environ['REDIS_URL'])

@app.task
def add(x, y):
    return x + y
```

## Ruby (redis-rb)

```ruby
require "redis"

redis = Redis.new(url: ENV["REDIS_URL"])

redis.set("key", "value")
puts redis.get("key")
```

## Ruby (Sidekiq)

```ruby
require "sidekiq"

Sidekiq.configure_server do |config|
  config.redis = { url: ENV["REDIS_URL"] }
end

Sidekiq.configure_client do |config|
  config.redis = { url: ENV["REDIS_URL"] }
end
```

## Go (go-redis)

```go
package main

import (
    "context"
    "fmt"
    "os"
    "github.com/redis/go-redis/v9"
)

func main() {
    opt, _ := redis.ParseURL(os.Getenv("REDIS_URL"))
    client := redis.NewClient(opt)
    ctx := context.Background()

    client.Set(ctx, "key", "value", 0)
    val, _ := client.Get(ctx, "key").Result()
    fmt.Println(val)
}
```

## External connections (local development)

External connections require TLS (`rediss://` scheme) and authentication. Enable external access in the Dashboard first (add your IP to the allow list).

```bash
# Connect via redis-cli
redis-cli --tls -u rediss://red-xxx:6379 -a YOUR_PASSWORD
```

For local development, consider using a local Redis/Valkey instance and only connecting to the Render instance in staging/production.
