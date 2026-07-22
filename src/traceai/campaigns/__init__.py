"""Experiment campaigns for security, availability, and overhead evaluation."""

from pathlib import Path


def run_campaign(campaign_type: str, profile: str, quick: bool, output: Path) -> int:
    """Dispatch to the appropriate campaign runner."""
    if campaign_type == "security":
        from traceai.campaigns.security import run_security_campaign
        return run_security_campaign(profile, quick, output)
    elif campaign_type == "availability":
        from traceai.campaigns.availability import run_availability_campaign
        return run_availability_campaign(profile, quick, output)
    elif campaign_type == "overhead":
        from traceai.campaigns.overhead import run_overhead_campaign
        return run_overhead_campaign(profile, quick, output)
    else:
        raise ValueError(f"Unknown campaign type: {campaign_type}")
