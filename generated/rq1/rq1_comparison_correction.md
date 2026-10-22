# RQ1 Comparison Correction: Separate Inventory Universes

## Problem

The previous metric reported:

> Syft/Trivy Jaccard = 0.1584 (Syft: 101, Trivy: 16, Intersection: 16)

This compared **different inventory universes**:
- Syft scanned the installed Python environment (101 transitive packages)
- Trivy scanned requirements-exact.txt (16 direct dependencies)

A Jaccard index is only meaningful when both tools scan the **same target**.

## Correction

### Direct Dependency Universe (requirements-exact.txt)

| Metric | Value |
|--------|-------|
| Expected direct deps | 16 |
| Trivy detected | 16 |
| Syft detected (matching) | 16 |
| Trivy recall | 1.0000 |
| Syft recall | 1.0000 |
| Trivy/Syft Jaccard (same universe) | 1.0000 |

### Installed Environment Universe (.venv/Lib/site-packages)

| Metric | Value |
|--------|-------|
| Syft detected | 101 |
| Trivy status | NOT_COMPARABLE_ON_WINDOWS |
| Jaccard | NOT_COMPARABLE |

**Note:** Trivy's pip scanner requires a requirements/lock file. It does not enumerate installed site-packages on Windows. The comparison between Syft's 101 installed packages and Trivy's 16 direct dependencies is a universe mismatch, not tool disagreement.

## Key Insight

The previous Jaccard of 0.1584 was not "low agreement" between the tools.
It was an artifact of comparing apples (installed env) to oranges (manifest).
When both tools scan the same target, their agreement is substantially higher.
