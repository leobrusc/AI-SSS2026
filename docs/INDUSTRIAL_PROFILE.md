# TraceAI Industrial Profile Documentation

## ⚠️ Critical Notice

> **Industrial results CANNOT be claimed without execution proof.**
>
> The industrial profile requires externally provisioned infrastructure that must be operational, configured, and producing verifiable evidence during experiment execution. Simply configuring the profile without running it against live infrastructure does NOT constitute industrial validation.
>
> Any paper, report, or claim referencing industrial-profile results MUST include the campaign result manifest with cryptographic proof of execution against the required infrastructure.

---

## Overview

The `industrial` profile validates TraceAI's assurance mechanisms in a production-representative environment with:
- Container registry with vulnerability scanning (Harbor)
- CI/CD pipeline (GitLab)
- Container orchestration (K3s / Kubernetes)
- Software composition analysis platform (Dependency-Track)
- Keyless signing with transparency log (Cosign + Sigstore)

This profile exercises the full trust chain: from artifact creation through registry storage, vulnerability analysis, attestation signing, and deployment gate evaluation in a real Kubernetes cluster.

---

## Required Infrastructure

### Harbor (Container Registry)

| Component | Requirement |
|-----------|-------------|
| Version | Harbor 2.9+ |
| Purpose | Store and scan container images; host CycloneDX BOMs |
| Features needed | Vulnerability scanning (Trivy scanner), robot accounts, project-level access |
| Network | HTTPS endpoint accessible from experiment host and K3s cluster |

**Setup**:
1. Create a Harbor project for TraceAI (e.g., `traceai`)
2. Create a robot account with push/pull permissions
3. Enable automatic vulnerability scanning on push
4. Configure HTTPS with valid TLS certificate (or add CA to trust store)

### GitLab (CI/CD)

| Component | Requirement |
|-----------|-------------|
| Version | GitLab 16.0+ (CE or EE) |
| Purpose | Store source code, run CI/CD pipelines, trigger deployments |
| Features needed | CI/CD pipelines, container registry integration, API access |
| Network | HTTPS endpoint accessible from experiment host |

**Setup**:
1. Create a project for TraceAI
2. Configure CI/CD variables for Harbor and Dependency-Track credentials
3. Create a personal access token with `api` and `read_registry` scopes
4. Configure runner with Docker executor (for building images)

### K3s (Lightweight Kubernetes)

| Component | Requirement |
|-----------|-------------|
| Version | K3s v1.28+ (or any Kubernetes 1.28+) |
| Purpose | Deploy and manage the inference service in containers |
| Features needed | Namespace isolation, resource limits, configmaps, RBAC |
| Network | API server accessible from experiment host; nodes can pull from Harbor |

**Setup**:
1. Install K3s on a Linux host (or use existing Kubernetes cluster)
2. Create `traceai` namespace: `kubectl create namespace traceai`
3. Apply manifests from `manifests/k3s/`:
   - `namespace.yaml`
   - `resource-limits.yaml`
   - `configmap.yaml`
   - `deployment.yaml`
   - `service.yaml`
4. Configure image pull secret for Harbor
5. Export kubeconfig for experiment host access

### Dependency-Track (SCA Platform)

| Component | Requirement |
|-----------|-------------|
| Version | Dependency-Track 4.9+ |
| Purpose | Ingest CycloneDX BOMs, track vulnerabilities, produce analysis results |
| Features needed | BOM upload API, vulnerability analysis, policy evaluation |
| Network | HTTPS endpoint accessible from experiment host |

**Setup**:
1. Deploy Dependency-Track (see `docker/dependency-track.compose.yml` for reference)
2. Create a TraceAI project in the Dependency-Track UI
3. Generate an API key with BOM upload and analysis permissions
4. Configure vulnerability data sources (NVD, OSV, GitHub Advisories)
5. Allow time for initial vulnerability database sync (can take hours)

### Cosign (Sigstore Signing)

| Component | Requirement |
|-----------|-------------|
| Version | Cosign 2.2+ |
| Purpose | Sign container images and attestations with keyless signing |
| Features needed | Keyless signing (Fulcio + Rekor), image verification |
| Network | Access to `fulcio.sigstore.dev` and `rekor.sigstore.dev` |

**Setup**:
1. Install Cosign binary (verified against `tools.lock.json`)
2. Keyless signing requires OIDC identity provider (GitHub, Google, Microsoft)
3. Verify Sigstore endpoints are reachable:
   ```powershell
   cosign verify-blob --help  # Confirms binary works
   curl https://fulcio.sigstore.dev/api/v1/rootCert  # Confirms connectivity
   ```

---

## Environment Variables

All external service connections are configured via environment variables. Create a `.env` file from `.env.example`:

```bash
# Profile selection
TRACEAI_PROFILE=industrial

# Harbor Container Registry
HARBOR_URL=https://harbor.example.com
HARBOR_PROJECT=traceai
HARBOR_USERNAME=robot$traceai-ci
HARBOR_PASSWORD=<robot-account-token>

# Dependency-Track
DEPENDENCY_TRACK_URL=https://dtrack.example.com
DEPENDENCY_TRACK_API_KEY=<api-key>

# GitLab
GITLAB_URL=https://gitlab.example.com
GITLAB_TOKEN=<personal-access-token>

# Kubernetes
KUBECONFIG=C:\Users\leolima\.kube\config-traceai

# Cosign (keyless — uses OIDC, no static key needed)
COSIGN_KEY=  # Leave empty for keyless
COSIGN_PASSWORD=  # Leave empty for keyless

# Resource Limits
TRACEAI_MAX_HOST_GPU_MEMORY_PERCENT=80
TRACEAI_MAX_HOST_RAM_PERCENT=80
TRACEAI_MAX_TEST_DURATION_SECONDS=1800
```

### Variable Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `TRACEAI_PROFILE` | Yes | Must be `industrial` |
| `HARBOR_URL` | Yes | Harbor base URL (https) |
| `HARBOR_PROJECT` | Yes | Harbor project name |
| `HARBOR_USERNAME` | Yes | Robot account or user with push/pull |
| `HARBOR_PASSWORD` | Yes | Credentials for Harbor |
| `DEPENDENCY_TRACK_URL` | Yes | Dependency-Track API base URL |
| `DEPENDENCY_TRACK_API_KEY` | Yes | API key with upload permissions |
| `GITLAB_URL` | Yes | GitLab instance URL |
| `GITLAB_TOKEN` | Yes | Personal access token (api scope) |
| `KUBECONFIG` | Yes | Path to kubeconfig file for K3s/K8s |
| `COSIGN_KEY` | No | Empty for keyless signing |
| `COSIGN_PASSWORD` | No | Empty for keyless signing |

---

## Connectivity Requirements

All infrastructure must be reachable from the experiment host. Verify connectivity before running campaigns:

```powershell
# Harbor
Invoke-RestMethod -Uri "$env:HARBOR_URL/api/v2.0/ping" -Method Get

# Dependency-Track
Invoke-RestMethod -Uri "$env:DEPENDENCY_TRACK_URL/api/version" -Method Get

# GitLab
Invoke-RestMethod -Uri "$env:GITLAB_URL/api/v4/version" `
  -Headers @{"PRIVATE-TOKEN" = $env:GITLAB_TOKEN}

# Kubernetes
kubectl --kubeconfig $env:KUBECONFIG cluster-info

# Sigstore (for cosign keyless)
Invoke-WebRequest -Uri "https://fulcio.sigstore.dev/api/v1/rootCert" -UseBasicParsing
Invoke-WebRequest -Uri "https://rekor.sigstore.dev/api/v1/log" -UseBasicParsing
```

The `traceai doctor --profile industrial` command performs all these checks automatically and reports any failures.

### Network Ports

| Service | Default Port | Protocol |
|---------|-------------|----------|
| Harbor | 443 | HTTPS |
| Dependency-Track | 443 or 8080 | HTTPS/HTTP |
| GitLab | 443 | HTTPS |
| K3s API Server | 6443 | HTTPS |
| Fulcio | 443 | HTTPS |
| Rekor | 443 | HTTPS |

### Firewall / Proxy Considerations

If operating behind a corporate firewall or proxy:
- Configure `HTTPS_PROXY` and `NO_PROXY` environment variables
- Ensure proxy allows connections to Sigstore endpoints
- Harbor, GitLab, and Dependency-Track should ideally be on the internal network (no proxy needed)
- K3s nodes must be able to pull images from Harbor without proxy interference

---

## Evidence That Must Be Produced

The industrial profile campaign must produce the following evidence artifacts to constitute valid industrial execution:

### 1. Campaign Result Manifest

```json
{
  "campaign_id": "security-industrial-20260722-...",
  "profile": "industrial",
  "infrastructure": {
    "harbor_url": "https://harbor.example.com",
    "harbor_reachable": true,
    "dependency_track_url": "https://dtrack.example.com",
    "dependency_track_reachable": true,
    "gitlab_url": "https://gitlab.example.com",
    "gitlab_reachable": true,
    "kubernetes_cluster": true,
    "kubernetes_namespace": "traceai",
    "cosign_keyless": true
  },
  "trials": [...],
  "trials_hash": "sha256:...",
  "environment_hash": "sha256:..."
}
```

### 2. Container Image Evidence

- Image pushed to Harbor with tag: `{HARBOR_URL}/{HARBOR_PROJECT}/traceai-inference:{version}`
- Image signed with Cosign (keyless): signature and attestation in registry
- Harbor vulnerability scan results available via API
- Image digest recorded in campaign manifest

### 3. BOM Upload Evidence

- CycloneDX BOM uploaded to Dependency-Track
- Dependency-Track analysis completed (vulnerability count recorded)
- BOM digest matches the signed attestation subject

### 4. Kubernetes Deployment Evidence

- Pod successfully deployed in `traceai` namespace
- Resource limits enforced (CPU/memory from `resource-limits.yaml`)
- Configuration drift detected when configmap is modified
- Pod logs showing gate evaluation results

### 5. Signing and Attestation Evidence

- Cosign signature stored in registry (verifiable via `cosign verify`)
- Rekor transparency log entry (inclusion proof)
- Attestation with subjects: model digest, BOM digest, configuration digest
- Signature timestamp within `validity_hours` (72h for industrial)

### 6. Environment Snapshot

- `environment.json` with `profile: "industrial"`
- All external service checks passing
- Tool versions matching `tools.lock.json`
- Kubernetes cluster info captured

---

## What Constitutes Valid Industrial Execution

✅ **Valid claims require ALL of the following**:
1. Campaign result manifest with `profile: "industrial"`
2. All infrastructure connectivity checks passing (`traceai doctor --profile industrial`)
3. Container image pushed to and signed in Harbor
4. BOM uploaded to and analyzed by Dependency-Track
5. Inference service deployed to K3s/Kubernetes
6. Gate evaluation performed against live signed artifacts
7. All trial results include infrastructure evidence fields
8. Result hash chain is intact and verifiable

❌ **The following do NOT constitute industrial validation**:
- Running with `--profile industrial` but with mocked/disabled external services
- Configuring environment variables but never connecting to the services
- Running the local profile and relabeling results as industrial
- Producing results without the infrastructure evidence fields
- Cherry-picking individual scenarios without full campaign execution

---

## Campaign Execution (Industrial)

```powershell
# 1. Set execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# 2. Activate environment
.\.venv\Scripts\Activate.ps1

# 3. Verify infrastructure
traceai doctor --profile industrial

# 4. Build and push container image
.\scripts\run_all.ps1 -Profile industrial

# 5. Or run campaigns individually
traceai campaign security --profile industrial
traceai campaign availability --profile industrial
traceai campaign overhead --profile industrial

# 6. Analyze results
traceai analyze --profile industrial
```

### Trial Parameters (Industrial)

| Parameter | Value |
|-----------|-------|
| Full trials | 30 |
| Quick trials | 3 |
| Requests per trial (full) | 200 |
| Requests per trial (quick) | 20 |
| Warmup requests | 10 |
| Max test duration | 1800 seconds |
| Service workers | 2 |
| Max concurrency | 8 |

---

## Troubleshooting

### Harbor Image Push Fails

```powershell
# Login to Harbor
docker login $env:HARBOR_URL -u $env:HARBOR_USERNAME -p $env:HARBOR_PASSWORD

# Verify project exists
Invoke-RestMethod -Uri "$env:HARBOR_URL/api/v2.0/projects/$env:HARBOR_PROJECT" `
  -Headers @{Authorization = "Basic $([Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${env:HARBOR_USERNAME}:${env:HARBOR_PASSWORD}")))"}
```

### Dependency-Track BOM Upload Fails

```powershell
# Check API connectivity
Invoke-RestMethod -Uri "$env:DEPENDENCY_TRACK_URL/api/v1/project" `
  -Headers @{"X-Api-Key" = $env:DEPENDENCY_TRACK_API_KEY}
```

### Kubernetes Pod Not Starting

```powershell
kubectl --kubeconfig $env:KUBECONFIG -n traceai get pods
kubectl --kubeconfig $env:KUBECONFIG -n traceai describe pod <pod-name>
kubectl --kubeconfig $env:KUBECONFIG -n traceai logs <pod-name>
```

### Cosign Keyless Signing Fails

Keyless signing requires an OIDC token. In CI environments, use workload identity. For manual execution:
```powershell
# This will open a browser for OIDC authentication
cosign sign --yes "$env:HARBOR_URL/$env:HARBOR_PROJECT/traceai-inference:latest"
```
