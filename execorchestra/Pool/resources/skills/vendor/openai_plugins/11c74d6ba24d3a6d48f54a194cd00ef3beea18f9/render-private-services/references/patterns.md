# Private Service Patterns

## Microservice Topology

The most common private service pattern is a **public gateway + internal microservices**:

```
Internet → [Web Service: gateway] → Private Network → [pserv: user-service]
                                                    → [pserv: billing-service]
                                                    → [pserv: notification-service]
```

The gateway (web service) is the only public-facing service. All internal services use `type: pserv` and communicate over the private network.

### Wiring in Blueprints

Each internal service exposes its address via `fromService`:

```yaml
envVars:
  - key: USER_SERVICE_URL
    fromService:
      name: user-service
      type: pserv
      property: hostport
```

The gateway concatenates protocol + hostport in its code:

```javascript
const userServiceUrl = `http://${process.env.USER_SERVICE_URL}`;
```

## gRPC Setup

Private services support any protocol, including gRPC:

1. Configure your gRPC server to listen on `0.0.0.0:<PORT>` (use the `PORT` env var or any non-restricted port)
2. Set `type: pserv` in the Blueprint
3. Consumers connect via `<service-name>:<port>` using a gRPC client

```yaml
services:
  - type: pserv
    name: grpc-service
    runtime: go
    plan: starter
    region: oregon
    buildCommand: go build -o server .
    startCommand: ./server
    envVars:
      - key: GRPC_PORT
        value: "50051"
```

Consumer wiring:

```yaml
envVars:
  - key: GRPC_SERVICE_ADDR
    fromService:
      name: grpc-service
      type: pserv
      property: hostport
```

**Note:** gRPC uses HTTP/2 over the private network. No TLS is needed for internal traffic (the private network is encrypted at the infrastructure level).

## Sidecar Pattern

Run supporting infrastructure (metrics collectors, log aggregators, proxies) as private services:

```yaml
services:
  - type: pserv
    name: otel-collector
    runtime: docker
    plan: starter
    region: oregon
    dockerfilePath: ./collector/Dockerfile
    startCommand: otelcol --config /etc/otel-config.yaml
```

Application services send telemetry to `otel-collector:<port>` on the private network.

## Health Checks for Private Services

Private services support health checks via the private network. Configure a health check path if your service exposes an HTTP endpoint:

```yaml
services:
  - type: pserv
    name: internal-api
    healthCheckPath: /health
```

For non-HTTP services (gRPC, TCP), Render checks that the process is running and the port is bound. There is no custom health check for non-HTTP protocols.

## Port Binding

- Private services **must** bind to at least one port
- Bind to `0.0.0.0`, not `127.0.0.1` or `localhost`
- The `PORT` env var defaults to `10000`, but you can use any non-restricted port
- Multiple ports: your service can listen on multiple ports, but `fromService` only exposes the primary port via `property: port`

### Restricted ports

System ports (typically 0-1023) may be restricted. Use ports >= 1024 for your services.

## Private Service vs Web Service

If you need public access **and** internal access, use a **web service**. Web services get both a public URL and an internal hostname on the private network.

Private services are strictly for internal traffic—they have no public URL and no `onrender.com` subdomain.
