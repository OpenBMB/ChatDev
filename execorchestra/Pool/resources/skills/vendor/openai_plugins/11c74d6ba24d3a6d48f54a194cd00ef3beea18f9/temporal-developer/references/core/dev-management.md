# Development Server and Worker Management

## Server Management

Before starting workers or workflows, you MUST start a local dev server, using the Temporal CLI:

```bash
temporal server start-dev # Start this in the background.
```

It is perfectly OK for this process to be shared across multiple projects / left running as you develop your Temporal code.

## Worker Management Details

### Starting Workers

How you start a worker is project-dependent, but generally Temporal code should have a program entrypoint which starts a worker. If your project doesn't, you should define it.

When you need a new worker, you should start it in the background (and preferrably have it log somewhere you can check), and then remember its PID so you can kill / clean it up later.

**Best practice**: As far as local development goes, run only ONE worker instance with the latest code. Don't keep stale workers (running old code) around.


### Cleanup

**Always kill workers when done.** Don't leave workers running.
