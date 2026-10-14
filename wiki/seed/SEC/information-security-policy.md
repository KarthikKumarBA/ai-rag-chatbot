---
title: Information Security Policy
classification: internal
labels: security, policy, access
author: meera
updated_at: 2026-06-30 10:00
---
## Access Control

Multi-factor authentication (MFA) is mandatory for all company accounts. Sign-in goes through the company single sign-on (SSO).
Access follows least privilege and is reviewed every quarter by each team manager.

## Passwords

Passwords must be at least **14 characters** long and stored in the company password manager.
Never reuse passwords across services. Passwords are changed only when a compromise is suspected, not on a fixed schedule.

## Secrets Management

Never commit secrets such as API keys, tokens or database credentials to Git.
Store secrets in the company vault. Any exposed secret must be rotated within **24 hours**.

## Laptops

Company laptops must use full-disk encryption, lock automatically after 5 minutes of inactivity, and install operating system updates within 7 days of release.

## Data Classification

| Class | Examples | Who can see it |
|---|---|---|
| Public | Marketing pages, this wiki's public pages | Everyone |
| Internal | Runbooks, policies | All employees |
| Confidential | Salaries, security assessments, budgets | Named groups only |
