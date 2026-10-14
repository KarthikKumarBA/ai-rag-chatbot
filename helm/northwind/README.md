# Northwind Helm chart

Deploys the Northwind Wiki and the RAG assistant.

| Component | Exposed | Storage | Replicas |
|---|---|---|---|
| wiki | Ingress (EKS) or port-forward (local) | PVC: SQLite | 1 |
| rag | Internal ClusterIP only | PVC: Chroma | 1 |

## Secret (required, created outside the chart)

```bash
kubectl create secret generic northwind-secrets -n northwind \
  --from-literal=OPENAI_API_KEY=... \
  --from-literal=ANTHROPIC_API_KEY=... \
  --from-literal=WIKI_API_TOKEN=... \
  --from-literal=RAG_API_TOKEN=...
```

## Local (Docker Desktop kind)

```bash
helm upgrade --install northwind helm/northwind -n northwind --create-namespace \
  -f helm/northwind/values-local.yaml
```

## AWS EKS

Prerequisites: AWS Load Balancer Controller, EBS CSI driver add-on, `gp3` StorageClass
(`eks/gp3-storageclass.yaml`), images in ECR, an ACM certificate.

```bash
helm upgrade --install northwind helm/northwind -n northwind --create-namespace \
  -f helm/northwind/values-eks.yaml
```

For Bedrock instead of API keys, create an IRSA role with the Bedrock policy,
annotate the service account in `values-eks.yaml`, and set `LLM_PROVIDER` / `EMBEDDING_PROVIDER` to `bedrock`.

## Limitations

SQLite and Chroma use ReadWriteOnce volumes, so each component runs one replica.
For high availability, move the wiki to PostgreSQL and the vectors to pgvector or OpenSearch.
