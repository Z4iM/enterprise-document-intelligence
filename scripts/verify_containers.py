"""Build and verify isolated synthetic Compose projects without reading user env/data.

Owned test containers are stopped, never pruned; test volumes and credentials are retained
under an ignored run directory for inspection. No system Docker settings are changed.
"""

import argparse
import hashlib
import http.cookiejar
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path


def run(command, env, *, capture=False, input_text=None):
    return subprocess.run(
        command,
        env=env,
        check=True,
        text=True,
        input=input_text,
        capture_output=capture,
        encoding="utf-8",
    )


def http_check(command, env, port, *, semantic=False):
    """Exercise real frontend bridge/auth/upload/worker, with synthetic fixture accounts."""
    password = secrets.token_urlsafe(32)
    # stdin keeps even synthetic passwords out of the command line and output.
    program = f"""
from sqlalchemy import select
from app.database.database import SessionLocal
from app.database.models import User
from app.auth.api import passwords
with SessionLocal() as db:
    assert set(db.scalars(select(User.id))) == {{'edi-smoke-employee', 'edi-smoke-reviewer'}}
    db.get(User, 'edi-smoke-employee').password_hash = passwords.hash({password!r})
    db.get(User, 'edi-smoke-reviewer').password_hash = passwords.hash({password!r})
    db.commit()
"""
    run(command + ["exec", "-T", "api", "python", "-"], env, input_text=program)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )
    base = f"http://127.0.0.1:{port}"

    def request(path, *, data=None, headers=None):
        response = opener.open(
            urllib.request.Request(base + path, data=data, headers=headers or {}),
            timeout=60,
        )
        with response:
            return response.status, response.read()

    assert request("/api/bridge/ready")[0] == 200
    status, html = request("/")
    assert status == 200
    stylesheet = re.search(rb'href="([^\"]+\.css[^\"]*)"', html)
    assert stylesheet, "Expected a production CSS asset on the frontend page."
    assert request(stylesheet[1].decode())[0] == 200
    token = json.loads(request("/api/bridge/auth/csrf")[1])["csrf_token"]
    _, body = request(
        "/api/bridge/auth/login",
        data=json.dumps(
            {"email": "edi-smoke-employee@synthetic.test", "password": password}
        ).encode(),
        headers={
            "Content-Type": "application/json",
            "x-csrf-token": token,
            "Origin": base,
        },
    )
    assert json.loads(body)["user"]["role"] == "employee"
    token = json.loads(request("/api/bridge/auth/csrf")[1])["csrf_token"]
    original = (
        "Receipt\nMerchant: Synthetic Cafe\nإيصال تجريبي\nTotal: $175.00".encode()
    )
    boundary = "edi-verification-" + uuid.uuid4().hex
    multipart = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            'filename="synthetic-http-receipt.txt"\r\nContent-Type: text/plain\r\n\r\n'
        ).encode()
        + original
        + f"\r\n--{boundary}--\r\n".encode()
    )
    # Make the HTTP original distinct from the seeded smoke original's duplicate hash.
    multipart = multipart.replace(b"Synthetic Cafe", b"Synthetic HTTP Cafe")
    original = original.replace(b"Synthetic Cafe", b"Synthetic HTTP Cafe")
    status, body = request(
        "/api/bridge/documents/upload",
        data=multipart,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "x-csrf-token": token,
            "Origin": base,
        },
    )
    assert status == 202, f"Expected durable 202 intake, received {status}"
    identifier = json.loads(body)["document_id"]
    path = "/api/bridge/documents/" + identifier
    for _ in range(90):
        state = json.loads(request(path + "/processing")[1])["state"]
        if state == "completed":
            break
        assert state != "failed", "Synthetic HTTP processing failed."
        time.sleep(1)
    else:
        raise RuntimeError("Synthetic HTTP processing did not finish.")
    document = json.loads(request(path)[1])
    assert "إيصال تجريبي" in document["text_preview"]
    assert (
        hashlib.sha256(request(path + "/original")[1]).digest()
        == hashlib.sha256(original).digest()
    )
    assert document["review_status"] == "needs_review"
    run(command + ["stop"], env)
    run(command + ["up", "--no-build", "-d", "--wait", "--wait-timeout", "180"], env)
    # Persisted session and original remain usable after all services restart.
    assert json.loads(request(path)[1])["processing_status"] == "completed"
    assert request(path + "/original")[1] == original
    # Normal authenticated policy upload remains searchable with rule inference disabled.
    token = json.loads(request("/api/bridge/auth/csrf")[1])["csrf_token"]
    request(
        "/api/bridge/auth/logout",
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "x-csrf-token": token,
            "Origin": base,
        },
    )
    token = json.loads(request("/api/bridge/auth/csrf")[1])["csrf_token"]
    request(
        "/api/bridge/auth/login",
        data=json.dumps(
            {"email": "edi-smoke-reviewer@synthetic.test", "password": password}
        ).encode(),
        headers={
            "Content-Type": "application/json",
            "x-csrf-token": token,
            "Origin": base,
        },
    )
    token = json.loads(request("/api/bridge/auth/csrf")[1])["csrf_token"]
    policy_text = "تتطلب مصروفات الوجبات التي تتجاوز مائة دولار موافقة المدير."
    boundary = "edi-policy-" + uuid.uuid4().hex
    upload = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic-search-policy.txt"\r\nContent-Type: text/plain\r\n\r\n'.encode()
        + policy_text.encode()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    status, body = request(
        "/api/bridge/policies/upload",
        data=upload,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "x-csrf-token": token,
            "Origin": base,
        },
    )
    assert status == 202
    policy = json.loads(body)["policy_id"]
    for _ in range(90):
        state = json.loads(request(f"/api/bridge/policies/{policy}/index")[1])
        if state["state"] == "ready":
            break
        assert state["state"] != "failed", "Synthetic indexing failed."
        time.sleep(1)
    else:
        raise RuntimeError("Search index did not become ready.")
    status, body = request(
        "/api/bridge/evidence/search",
        data=json.dumps(
            {"query": "موافقة المدير للوجبات", "policy_ids": [policy]}
        ).encode(),
        headers={
            "Content-Type": "application/json",
            "x-csrf-token": token,
            "Origin": base,
        },
    )
    result = json.loads(body)
    assert status == 200 and result["results"][0]["quote"] == policy_text
    assert result["mode"] == ("hybrid" if semantic else "lexical")
    citation = result["results"][0]["citation_id"]
    assert (
        json.loads(request(f"/api/bridge/evidence/citations/{citation}")[1])["quote"]
        == policy_text
    )
    run(command + ["restart", "api"], env)
    for _ in range(30):
        try:
            if request("/api/bridge/ready")[0] == 200:
                break
        except (OSError, urllib.error.HTTPError):
            time.sleep(1)
    assert (
        json.loads(request(f"/api/bridge/evidence/citations/{citation}")[1])["quote"]
        == policy_text
    )
    assert request(f"/api/bridge/policies/{policy}/original")[1] == policy_text.encode()
    print("Policy upload/index/Arabic search/citation checks passed.", flush=True)
    print(
        "HTTP bridge/session/202 upload/worker/Arabic/original/restart checks passed.",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--docker", default=shutil.which("docker"))
    parser.add_argument("--run-id", default=uuid.uuid4().hex[:12])
    parser.add_argument(
        "--model-directory",
        help="Optional existing verified model directory, mounted read-only; never downloaded by the runner.",
    )
    parser.add_argument(
        "--phase", choices=["build", "default", "compact", "all"], default="all"
    )
    args = parser.parse_args()
    if not args.docker or not re.fullmatch(r"[a-f0-9]{12}", args.run_id):
        parser.error(
            "Supply a Docker executable and a 12-character hexadecimal run ID."
        )
    root = Path(__file__).resolve().parents[1]
    directory = root / ".local" / "container-verification" / args.run_id
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not directory.resolve().is_relative_to(root.resolve()):
        raise RuntimeError("Verification directory must stay inside the project.")
    directory.chmod(0o700)
    metadata = directory / "run.json"
    if metadata.exists():
        port = json.loads(metadata.read_text())["port"]
        assert isinstance(port, int) and 1024 < port < 65536
    else:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        metadata.write_text(json.dumps({"port": port}), encoding="utf-8")
    for name in ("postgres-password", "app-password"):
        target = directory / name
        if target.is_symlink() or (target.exists() and target.stat().st_nlink > 1):
            raise RuntimeError("Verification credentials cannot be links.")
        if not target.exists():
            target.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        target.chmod(0o444)
    empty = directory / "empty.env"
    empty.write_text("", encoding="utf-8")
    override = directory / "verification.yaml"
    backend = "edi-verification-backend:" + args.run_id
    frontend = "edi-verification-frontend:" + args.run_id
    override.write_text(
        "services:\n"
        + "".join(
            f"  {name}:\n    image: {backend}\n    environment:\n      EDI_ALLOWED_ORIGINS: http://127.0.0.1:{port}\n      EDI_RETRIEVAL_MODEL_DIR: {json.dumps('/srv/models/retrieval' if args.model_directory else '')}\n"
            + (
                f"    volumes:\n      - type: bind\n        source: {json.dumps(str(Path(args.model_directory).resolve()))}\n        target: /srv/models/retrieval\n        read_only: true\n"
                if args.model_directory
                else ""
            )
            for name in ("api", "worker", "migrate")
        )
        + f'  frontend:\n    image: {frontend}\n    ports: !override\n      - "127.0.0.1:{port}:3000"\n'
        + "secrets:\n"
        + "".join(
            f"  {key}:\n    file: {json.dumps(str(directory / name))}\n"
            for key, name in (
                ("postgres_password", "postgres-password"),
                ("app_password", "app-password"),
            )
        ),
        encoding="utf-8",
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("COMPOSE_")
    }
    env.update(
        COMPOSE_PARALLEL_LIMIT="1",
        PATH=str(Path(args.docker).parent) + os.pathsep + env["PATH"],
    )

    def compose(compact=False):
        command = [
            args.docker,
            "compose",
            "--project-directory",
            str(root),
            "--env-file",
            str(empty),
            "-p",
            f"edi-verify-{args.run_id}-{'compact' if compact else 'default'}",
            "-f",
            str(root / "compose.yaml"),
        ]
        if compact:
            command += ["-f", str(root / "compose.compact.yaml")]
        return command + ["-f", str(override)]

    print(
        f"Verification run: {args.run_id}; retained files: {directory}; loopback port: {port}",
        flush=True,
    )
    if args.phase in {"build", "all"}:
        # Serial builds avoid three identical backend builds competing on small machines.
        for service in ("api", "frontend"):
            print(f"Building {service} image...", flush=True)
            run(compose() + ["build", service], env)
    for compact in (False, True):
        name = "compact" if compact else "default"
        if args.phase not in {name, "all"}:
            continue
        command = compose(compact)
        config = json.loads(
            run(command + ["config", "--format", "json"], env, capture=True).stdout
        )
        services = config["services"]
        assert services["frontend"]["ports"] == [
            {
                "mode": "ingress",
                "target": 3000,
                "published": str(port),
                "protocol": "tcp",
                "host_ip": "127.0.0.1",
            }
        ]
        for service in ("api", "db", "migrate", "worker"):
            assert not services.get(service, {}).get("ports")
        if compact:
            assert "worker" not in services
        print(f"Starting isolated {name} profile...", flush=True)
        try:
            run(
                command + ["up", "--no-build", "-d", "--wait", "--wait-timeout", "180"],
                env,
            )
            run(command + ["exec", "-T", "api", "tesseract", "--list-langs"], env)
            run(command + ["exec", "-T", "api", "python", "-m", "app.jobs.smoke"], env)
            run(command + ["stop"], env)
            run(
                command + ["up", "--no-build", "-d", "--wait", "--wait-timeout", "180"],
                env,
            )
            run(
                command
                + ["exec", "-T", "api", "python", "-m", "app.jobs.smoke", "--verify"],
                env,
            )
            http_check(command, env, port, semantic=bool(args.model_directory))
            print(
                f"{name.capitalize()} profile: all container checks passed.", flush=True
            )
        except Exception:
            run(command + ["logs", "--no-color", "--tail", "40"], env)
            raise
        finally:
            run(command + ["stop"], env)


if __name__ == "__main__":
    main()
