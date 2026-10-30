"""Run synthetic PostgreSQL checks in an owned ephemeral loopback-only cluster.

Supply official PostgreSQL binaries; never install/start a Windows system service.
"""

import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bin", required=True)
    args = parser.parse_args()
    binary = Path(args.bin).resolve()
    suffix = ".exe" if os.name == "nt" else ""
    with tempfile.TemporaryDirectory(prefix="edi-pg-verification-") as directory:
        root = Path(directory).resolve()
        data = root / "cluster"
        options = (
            {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        )
        subprocess.run(
            [
                str(binary / ("initdb" + suffix)),
                "-D",
                str(data),
                "-U",
                "ediverify",
                "-A",
                "trust",
                "--encoding=UTF8",
                "--locale=C",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            **options,
        )
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with (root / "postgres.log").open("wb") as log:
            process = subprocess.Popen(
                [
                    str(binary / ("postgres" + suffix)),
                    "-D",
                    str(data),
                    "-h",
                    "127.0.0.1",
                    "-p",
                    str(port),
                    "-c",
                    "shared_buffers=16MB",
                    "-c",
                    "max_connections=20",
                ],
                stdout=log,
                stderr=log,
                **options,
            )
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("Temporary PostgreSQL could not start.")
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                            break
                    except OSError:
                        time.sleep(0.1)
                env = {
                    **os.environ,
                    "EDI_POSTGRES_TEST_URL": f"postgresql+psycopg://ediverify@127.0.0.1:{port}/postgres",
                    "PYTHON_DOTENV_DISABLED": "1",
                }
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "-q",
                        "tests/test_postgres_integration.py",
                    ],
                    env=env,
                    check=False,
                )
                if result.returncode == 0:
                    # Verify actual OS-process restart as well as unit-level lease recovery.
                    env.update(
                        EDI_DATABASE_URL=env["EDI_POSTGRES_TEST_URL"],
                        EDI_DATA_ROOT=str(root / "files"),
                        LLM_PROVIDER="disabled",
                        EDI_PROCESSING_MODE="external",
                    )
                    env.pop("GEMINI_API_KEY", None)
                    subprocess.run(
                        [sys.executable, "-m", "alembic", "upgrade", "head"],
                        env=env,
                        check=True,
                    )
                    worker = subprocess.Popen(
                        [sys.executable, "-m", "app.jobs.worker"],
                        env=env,
                        stdout=log,
                        stderr=log,
                        **options,
                    )
                    try:
                        subprocess.run(
                            [sys.executable, "-m", "app.jobs.smoke"],
                            env=env,
                            check=True,
                        )
                    finally:
                        worker.terminate()
                        worker.wait(timeout=10)
                    subprocess.run(
                        [
                            str(binary / ("pg_ctl" + suffix)),
                            "-D",
                            str(data),
                            "stop",
                            "-m",
                            "fast",
                            "-w",
                        ],
                        stdout=subprocess.DEVNULL,
                        check=True,
                        **options,
                    )
                    process.wait(timeout=10)
                    process = subprocess.Popen(
                        [
                            str(binary / ("postgres" + suffix)),
                            "-D",
                            str(data),
                            "-h",
                            "127.0.0.1",
                            "-p",
                            str(port),
                            "-c",
                            "shared_buffers=16MB",
                            "-c",
                            "max_connections=20",
                        ],
                        stdout=log,
                        stderr=log,
                        **options,
                    )
                    for _ in range(100):
                        ready = subprocess.run(
                            [
                                str(binary / ("pg_isready" + suffix)),
                                "-h",
                                "127.0.0.1",
                                "-p",
                                str(port),
                            ],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                            **options,
                        )
                        if ready.returncode == 0:
                            break
                        time.sleep(0.1)
                    subprocess.run(
                        [sys.executable, "-m", "app.jobs.smoke", "--verify"],
                        env=env,
                        check=True,
                    )
                    print(
                        "Actual PostgreSQL/worker process restart and checkpoint resume passed."
                    )
            finally:
                subprocess.run(
                    [
                        str(binary / ("pg_ctl" + suffix)),
                        "-D",
                        str(data),
                        "stop",
                        "-m",
                        "fast",
                        "-w",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    **options,
                )
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()  # Only the process created above.
                    process.wait()
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
