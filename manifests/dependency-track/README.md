# Dependency-Track Kubernetes Deployment

## Overview

Instructions for deploying [OWASP Dependency-Track](https://dependencytrack.org/) in a Kubernetes (k3s) cluster for SBOM analysis and vulnerability tracking.

## Prerequisites

- k3s cluster running with `kubectl` configured
- Namespace `traceai` created (see `../k3s/namespace.yaml`)
- Persistent storage provisioner available

## Deployment Steps

1. **Create the namespace** (if not already created):
   ```bash
   kubectl apply -f ../k3s/namespace.yaml
   ```

2. **Deploy the API Server**:
   ```bash
   kubectl apply -f dtrack-apiserver-deployment.yaml
   kubectl apply -f dtrack-apiserver-service.yaml
   ```

3. **Deploy the Frontend**:
   ```bash
   kubectl apply -f dtrack-frontend-deployment.yaml
   kubectl apply -f dtrack-frontend-service.yaml
   ```

4. **Verify deployment**:
   ```bash
   kubectl get pods -n traceai -l app=dependency-track
   ```

## Configuration

- API Server listens on port 8080 internally
- Frontend connects to the API server via the internal service URL
- Default admin credentials: `admin` / `admin` (change immediately after first login)

## Persistent Storage

Dependency-Track requires persistent storage for:
- The embedded H2 database (or configure an external PostgreSQL)
- Uploaded SBOMs and analysis results

## Integration with TraceAI

The CI pipeline uploads CycloneDX SBOMs to Dependency-Track after each build:
```bash
curl -X POST "http://dtrack-api:8080/api/v1/bom" \
  -H "X-Api-Key: ${DTRACK_API_KEY}" \
  -H "Content-Type: application/json" \
  -d @sbom.cdx.json
```

## Local Development

For local development, use the Docker Compose file:
```bash
docker compose -f ../../docker/dependency-track.compose.yml up -d
```
