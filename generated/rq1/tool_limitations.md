# RQ1 Tool Limitations

## Trivy

Trivy fs scan found 0 components. This occurs when Trivy does not detect a supported lockfile format in the project root. The project uses requirements.lock (pip freeze format) which may not be recognized by this Trivy version. This is a tool limitation, not evidence of absence.
