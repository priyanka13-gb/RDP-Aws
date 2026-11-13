# Local failure drill record

This was an intentional local exercise, not a production incident.

Image: `rdp-release:git-9b18a3109aa2`. Linux AMD64, UID 10001:10001.
Network disabled; no ports, mounts, AWS calls or database volumes.

| Observed at (UTC) | Scenario | Result |
| --- | --- | --- |
| 2026-11-13T16:58:20.338730+00:00 | healthy_baseline | /health 200, /ready 200; healthy |
| 2026-11-13T16:58:31.612495+00:00 | unhealthy_application | /health 503, /ready 200; unhealthy |
| 2026-11-13T16:58:42.360879+00:00 | failed_readiness | /health 200, /ready 503; healthy |
| 2026-11-13T16:58:42.834287+00:00 | startup_failure | exit 1 |
| 2026-11-13T16:58:53.057366+00:00 | healthy_recovery | /health 200, /ready 200; healthy |

All five scenarios passed. Only this run's labelled containers were removed.

Readiness failure left Docker liveness healthy, demonstrating why the ALB must
check `/ready`. Startup failure exited before serving requests. Recovery used
the original image command in a fresh container; Docker did not roll it back.

**AWS failures injected: none. ECS rollback: NOT VERIFIED.** The current
read-only AWS observation found no demo deployment, so the live drill is NO-GO.

Follow-up: establish an independently approved healthy deployment, then request
separate approval for the bounded rollback drill. Keep raw AWS data private.

Evidence: [local results](../../evidence/task30/local-drill.json),
[current snapshot](../../evidence/task30/current-monitor.json).
