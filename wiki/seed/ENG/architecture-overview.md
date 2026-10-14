---
title: Platform Architecture Overview
classification: internal
labels: architecture, kubernetes, aws
author: asha
updated_at: 2026-09-20 16:45
---
## Overview

The Northwind platform runs on **Amazon EKS** in the ap-south-1 (Mumbai) region, with a disaster-recovery copy in ap-southeast-1 (Singapore).

## Core Services

| Service | Purpose | Owner team |
|---|---|---|
| api-gateway | Public entry point, authentication, rate limiting | Platform |
| billing-api | Invoices, subscriptions and payments | Payments |
| user-service | Accounts, profiles and permissions | Identity |
| notification-service | Email, SMS and in-app notifications | Platform |

## Data Stores

- **payments-db**: PostgreSQL 16 (Amazon RDS, Multi-AZ) for billing data.
- **users-db**: PostgreSQL 16 for accounts.
- **Redis**: caching and rate-limit counters.
- **S3**: invoices and document storage, encrypted with KMS.

## Observability

Metrics go to Prometheus and Grafana, logs to OpenSearch, and traces to OpenTelemetry. Alerts route to the on-call engineer through the paging tool.
