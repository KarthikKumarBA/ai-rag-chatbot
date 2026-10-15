# Deploy Northwind to AWS EKS

The cluster, ECR repositories and the deploy role come from the **aws-infra** repository.

## GitHub settings (once)

Variables: `AWS_REGION`, `EKS_CLUSTER_NAME`, `ECR_REGISTRY`, `AWS_DEPLOY_ROLE_ARN`, `ALLOWED_CIDR` (your IP/32), `BEDROCK_ROLE_ARN` (optional).

Secrets: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (optional), `WIKI_API_TOKEN`, `RAG_API_TOKEN`.

## Deploy / remove

GitHub → **Actions** → **CD** → **Run workflow** → `deploy` or `uninstall`.

The run summary shows the wiki URL (an ALB that only your IP can open).

If your IP changes: update `ALLOWED_CIDR` and run `deploy` again.
