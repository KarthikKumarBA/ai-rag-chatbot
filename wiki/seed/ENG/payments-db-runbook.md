---
title: Payments Database Runbook
classification: internal
labels: runbook, database, payments
author: asha
updated_at: 2026-09-25 19:20
---
## Overview

payments-db is a PostgreSQL 16 cluster on Amazon RDS (Multi-AZ) used by billing-api.

## Health Checks

- Replication lag on the read replica must stay below 5 seconds.
- CPU above 80% for 10 minutes pages the Payments on-call engineer.
- Storage alerts fire at 80% usage; storage autoscaling is enabled up to 2 TB.

## Failover

RDS fails over to the standby automatically within 1-2 minutes.
For a manual failover, use "Reboot with failover" in the RDS console, then confirm that billing-api reconnects by checking its /health endpoint.
If the primary region is down, promote the cross-region read replica in ap-southeast-1 and update the DNS record payments-db.internal.

## Backups

Automated snapshots are taken daily and kept for 35 days. Point-in-time recovery is available for the last 7 days.

<!-- sensitive -->
## Break-Glass Access

Use only during a SEV1 when IAM authentication is unavailable.

- Connection string: postgres://payments_admin:Nw!Pay#2026-prod@payments-db.prod.internal:5432/payments
- Break-glass password: Nw!Pay#2026-prod
- Rotate the credential within 24 hours after any use.
<!-- /sensitive -->

## Contacts

Owner team: Payments. Escalation channel: #payments-oncall.
