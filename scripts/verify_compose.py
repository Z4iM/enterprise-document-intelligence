"""Validate real Compose configuration with isolated dummy secrets, never user .env files."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--compose", help="Optional official standalone Compose executable"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    command = [args.compose] if args.compose else ["docker", "compose"]
    with tempfile.TemporaryDirectory(prefix="edi-compose-verification-") as directory:
        project = Path(directory)
        secrets = project / ".local/container"
        secrets.mkdir(parents=True)
        for name in ("postgres-password", "app-password"):
            (secrets / name).write_text(
                "synthetic-configuration-only", encoding="utf-8"
            )
        (project / "empty.env").write_text("", encoding="utf-8")
        for compact in (False, True):
            invocation = command + [
                "--project-directory",
                str(project),
                "--env-file",
                str(project / "empty.env"),
                "-f",
                str(root / "compose.yaml"),
            ]
            if compact:
                invocation += ["-f", str(root / "compose.compact.yaml")]
            result = subprocess.run(
                invocation + ["config", "--format", "json"],
                check=True,
                capture_output=True,
                text=True,
            )
            services = json.loads(result.stdout)["services"]
            for name in ("db", "api", "worker", "migrate"):
                if name not in services:
                    assert compact and name == "worker"
                    continue
                assert not services[name].get("ports"), f"{name} must remain private"
            assert services["frontend"]["ports"][0]["host_ip"] == "127.0.0.1"
            assert services["api"]["read_only"]
            if "worker" in services:
                assert services["worker"]["read_only"]
            assert (
                services["api"]["depends_on"]["migrate"]["condition"]
                == "service_completed_successfully"
            )
            assert services["api"]["environment"]["EDI_PROCESSING_MODE"] == (
                "embedded" if compact else "external"
            )
            print(
                "Compact Compose configuration passed."
                if compact
                else "Default Compose configuration passed."
            )


if __name__ == "__main__":
    main()
