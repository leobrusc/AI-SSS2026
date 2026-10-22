"""Standard-library-only diagnostic packaging, including failed runs."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile


def package(output: Path, exit_code: int) -> tuple[Path, Path]:
    output = output.resolve()
    report_path = output / "validation_report.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    if exit_code or report.get("status") != "VALID_FOR_PUBLICATION":
        report["status"] = "NOT_VALID_FOR_PUBLICATION"
    report["pipeline_exit_code"] = exit_code
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    sums = output / "SHA256SUMS"
    files = sorted(p for p in output.rglob("*") if p.is_file() and p != sums)
    sums.write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(output).as_posix()}\n"
        for p in files), encoding="utf-8")
    archive = output.parent / f"traceai_a100_results_{output.name}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in [*files, sums]:
            tar.add(path, arcname=f"{output.name}/{path.relative_to(output).as_posix()}")
    checksum = archive.with_name(archive.name + ".sha256")
    checksum.write_text(f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n", encoding="utf-8")
    return archive, checksum


if __name__ == "__main__":
    archive, checksum = package(Path(sys.argv[1]), int(sys.argv[2]))
    print("RETURN THESE TWO FILES")
    print(archive)
    print(checksum)
