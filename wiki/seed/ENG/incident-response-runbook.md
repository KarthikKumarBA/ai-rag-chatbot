---
title: Incident Response Runbook
classification: internal
labels: incident, on-call, runbook
author: meera
updated_at: 2026-09-18 08:40
---
## Severity Levels

| Severity | Definition | Response time |
|---|---|---|
| SEV1 | Full outage of a customer-facing service, or confirmed data loss | 15 minutes, 24x7 |
| SEV2 | A major feature is degraded for many customers | 30 minutes, 24x7 |
| SEV3 | Minor degradation with a workaround | Next business day |
| SEV4 | Cosmetic or internal-only issue | Team backlog |

## On-Call Rotation

The rotation is weekly, with handover every **Monday at 10:00 IST**. Each rotation has a primary and a secondary engineer.
A page must be acknowledged within **5 minutes**. Unacknowledged pages escalate to the secondary engineer, and after 15 minutes to the engineering manager.

## Incident Roles

- **Incident Commander (IC)**: coordinates the response and makes decisions.
- **Communications Lead**: posts updates every 30 minutes for SEV1 and SEV2 in #incidents and on the status page.
- **Subject Matter Experts**: investigate and apply fixes.

## Response Steps

1. Acknowledge the page.
2. Declare the incident in #incidents with a severity level.
3. Assign an Incident Commander.
4. Mitigate first (rollback, failover) before searching for the root cause.
5. Update the status page.
6. Resolve and monitor for 30 minutes before closing.

## Postmortem

A blameless postmortem is required for every **SEV1 and SEV2** incident, published within **5 business days**.
Action items are tracked in Jira, each with an owner and a due date.
