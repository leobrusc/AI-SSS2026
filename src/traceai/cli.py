"""Command-line interface for TraceAI."""

import argparse
import sys
from pathlib import Path


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="traceai",
        description="TraceAI: Runtime-Aware Assurance for LLM Pipelines",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s 0.1.0"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Doctor command
    doctor_parser = subparsers.add_parser("doctor", help="Run environment audit")
    doctor_parser.add_argument(
        "--profile", choices=["local", "container", "industrial"], default="local"
    )
    doctor_parser.add_argument("--output", type=Path, default=Path("generated"))

    # Audit command
    audit_parser = subparsers.add_parser("audit", help="Run evidence audit")
    audit_parser.add_argument("--profile", default="local")
    audit_parser.add_argument("--output", type=Path, default=Path("generated"))

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start inference service")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--profile", default="local")

    # Generate BOM command
    bom_parser = subparsers.add_parser("bom", help="Generate CycloneDX BOM")
    bom_parser.add_argument("--profile", default="local")
    bom_parser.add_argument("--output", type=Path, default=Path("generated"))

    # Campaign commands
    campaign_parser = subparsers.add_parser("campaign", help="Run experiment campaign")
    campaign_parser.add_argument(
        "type", choices=["security", "availability", "overhead"]
    )
    campaign_parser.add_argument("--profile", default="local")
    campaign_parser.add_argument("--quick", action="store_true")
    campaign_parser.add_argument("--output", type=Path, default=Path("results"))

    # RQ1 campaign
    rq1_parser = subparsers.add_parser("rq1-campaign", help="Run RQ1 traceability campaign")
    rq1_parser.add_argument("--profile", default="local")
    rq1_parser.add_argument("--quick", action="store_true")
    rq1_parser.add_argument("--output", type=Path, default=Path("results"))

    # RQ3 campaign
    rq3_parser = subparsers.add_parser("rq3-campaign", help="Run RQ3 vulnerability/VEX campaign")
    rq3_parser.add_argument("--profile", default="local")
    rq3_parser.add_argument("--quick", action="store_true")
    rq3_parser.add_argument("--output", type=Path, default=Path("results"))

    # RQ4 campaign
    rq4_parser = subparsers.add_parser("rq4-campaign", help="Run RQ4 availability campaign (real inference)")
    rq4_parser.add_argument("--profile", default="local")
    rq4_parser.add_argument("--quick", action="store_true")
    rq4_parser.add_argument("--mode", choices=["smoke", "experimental", "publication"], default="experimental")
    rq4_parser.add_argument("--output", type=Path, default=Path("results"))

    # Validate publication
    validate_parser = subparsers.add_parser("validate-publication", help="Validate publication readiness")
    validate_parser.add_argument("--profile", default="local")
    validate_parser.add_argument("--research-question", required=True,
                                 choices=["RQ1", "RQ2", "RQ3", "RQ4"])
    validate_parser.add_argument("--output", type=Path, default=Path("generated"))

    # Publication readiness
    readiness_parser = subparsers.add_parser("publication-readiness", help="Publication readiness report")
    readiness_parser.add_argument("--profile", default="local")
    readiness_parser.add_argument("--output", type=Path, default=Path("generated"))

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze campaign results")
    analyze_parser.add_argument("--profile", default="local")
    analyze_parser.add_argument("--input", type=Path, default=Path("results"))
    analyze_parser.add_argument("--output", type=Path, default=Path("generated"))

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "doctor":
        from traceai.environment import run_doctor
        return run_doctor(args.profile, args.output)
    elif args.command == "audit":
        from traceai.audit import run_audit
        return run_audit(args.profile, args.output)
    elif args.command == "serve":
        from traceai.service.app import start_server
        start_server(args.host, args.port, args.profile)
        return 0
    elif args.command == "bom":
        from traceai.bom.cyclonedx_builder import generate_bom
        return generate_bom(args.profile, args.output)
    elif args.command == "campaign":
        from traceai.campaigns import run_campaign
        return run_campaign(args.type, args.profile, args.quick, args.output)
    elif args.command == "rq1-campaign":
        from traceai.campaigns.rq1 import run_rq1_campaign
        return run_rq1_campaign(args.profile, args.quick, args.output)
    elif args.command == "rq3-campaign":
        from traceai.campaigns.rq3 import run_rq3_campaign
        return run_rq3_campaign(args.profile, args.quick, args.output)
    elif args.command == "rq4-campaign":
        from traceai.campaigns.rq4 import run_rq4_campaign
        return run_rq4_campaign(args.profile, args.quick, args.mode, args.output)
    elif args.command == "validate-publication":
        from traceai.publication import validate_publication
        return validate_publication(args.research_question, args.profile, args.output)
    elif args.command == "publication-readiness":
        from traceai.publication import publication_readiness
        return publication_readiness(args.profile, args.output)
    elif args.command == "analyze":
        from traceai.analysis import run_analysis
        return run_analysis(args.profile, args.input, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
