---
title: Deployment Guide
classification: internal
labels: deployment, ci-cd, release
author: asha
updated_at: 2026-09-05 12:10
---
## Environments

- **dev**: deployed automatically on every merge to main.
- **staging**: deployed automatically after the dev tests pass.
- **production**: promoted manually from staging.

## Production Requirements

Every production deployment needs:
- a change ticket in ServiceDesk,
- a pull request approved by **2 reviewers**,
- all CI checks green,
- a 24-hour soak in staging for major releases.

## Deployment Windows

Production deployments are allowed Monday to Thursday between 10:00 and 17:00 IST.
Deployments on **Friday after 15:00 IST** and on weekends are frozen, except emergency fixes approved by the engineering manager.
There is a full code freeze during the last week of December.

## Canary Releases

A new version first receives **10% of traffic for 30 minutes**.
It is promoted to 100% only if the error rate stays below 1% and p95 latency stays within 10% of the baseline.

## Rollback

If the canary fails, or a SEV1 or SEV2 incident starts after a deployment, roll back immediately with
`kubectl rollout undo deployment/<name> -n <namespace>` and notify the #deployments channel.
