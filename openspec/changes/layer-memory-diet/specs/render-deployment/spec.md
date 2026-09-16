# render-deployment — delta for layer-memory-diet

## ADDED Requirements

### Requirement: Web workers are recycled
Gunicorn SHALL restart each worker after a bounded number of requests
(`--max-requests` with `--max-requests-jitter`), with both numbers tunable through
environment variables declared in `render.yaml`, so that allocator fragmentation left by
large requests cannot accumulate for the life of the process.

#### Scenario: Worker recycles without dropping requests
- **WHEN** a worker reaches its request budget
- **THEN** it finishes its in-flight requests, exits, and the master has already started its replacement

#### Scenario: Budget tunable without rebuild
- **WHEN** an operator sets `GUNICORN_MAX_REQUESTS` or `GUNICORN_MAX_REQUESTS_JITTER` in the Render dashboard and restarts the service
- **THEN** gunicorn applies the new budget without an image rebuild
