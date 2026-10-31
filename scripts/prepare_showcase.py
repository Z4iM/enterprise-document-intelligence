"""Export public source to a new sandbox; optionally install fresh demo dependencies.

Never reads project dotenv files, copies working databases, or starts public services.
Pending M7 files are included explicitly so an uncommitted review can be rehearsed.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PENDING_FILES = {
    "scripts/prepare_showcase.py",
    "tests/test_showcase_preparation.py",
    "frontend/e2e/showcase.spec.ts",
    "frontend/src/lib/investigation-reasons.ts",
    "docs/SHOWCASE.md",
    "docs/DEMO_SCRIPT.md",
    "docs/PORTFOLIO.md",
    "docs/benchmarks/showcase-m7.json",
}
PRIVATE_NAMES = {"edi_codex_master_prompt.md", "edi_codex_agents_template.md", ".npmrc", ".pypirc", "auth.json", "id_rsa", "id_ed25519"}
PRIVATE_PARTS = {".git", ".venv", ".local", ".codex", ".agents", ".claude", "data", "node_modules", ".next"}


def git(root, *arguments):
    return subprocess.check_output(["git", "-C", str(root), *arguments])


def public_files(root):
    tracked = set(git(root, "ls-files", "-z").decode().split("\0")) - {""}
    pending = set(
        git(root, "ls-files", "--others", "--exclude-standard", "-z")
        .decode()
        .split("\0")
    )
    selected = tracked | {
        name for name in pending if name in PENDING_FILES or name.startswith("docs/demo/")
    }
    for name in sorted(selected):
        path = Path(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or (PRIVATE_PARTS.intersection(part.casefold() for part in path.parts) and name != "tests/data/policy_benchmark.json")
            or path.name.casefold() in PRIVATE_NAMES
            or any(part.casefold().startswith(".env") and part.casefold() != ".env.example" for part in path.parts)
            or path.suffix.casefold() in {".db", ".sqlite", ".sqlite3", ".pem", ".key", ".onnx", ".safetensors"}
        ):
            raise ValueError(f"Refusing non-public source path: {name}")
        source = root / path
        if (
            source.is_symlink()
            or any(parent.is_symlink() or parent.is_junction() for parent in source.parents if parent != root and parent.is_relative_to(root))
            or not source.resolve().is_relative_to(root.resolve())
            or not source.is_file()
            or source.stat().st_nlink != 1
        ):
            raise ValueError(f"Source must be an ordinary repository file: {name}")
        yield name


def prepare(root, destination):
    root = root.resolve()
    destination = destination.resolve()
    if destination.exists() or destination.is_relative_to(root):
        raise ValueError("Choose a nonexistent directory outside the repository.")
    names = list(public_files(root))  # Reject unsafe paths before creating anything.
    source = destination / "source"
    source.mkdir(parents=True)
    hashes = {}
    for name in names:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
        hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "base_commit": git(root, "rev-parse", "HEAD").decode().strip(),
        "working_tree_changes": bool(git(root, "status", "--porcelain")),
        "scope": "Public working-source export, not a published release or cold-cache clone.",
        "files_sha256": hashes,
        "data": "No user dotenv, databases, uploads, models or credentials exported.",
    }
    (destination / "source-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return source


def install_environment(destination):
    """Allow only ordinary OS lookup variables; drop provider/config credentials."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "HOME", "USERPROFILE", "COMSPEC", "PATHEXT"}
    }
    temporary = destination / "temporary"
    temporary.mkdir(exist_ok=True)
    environment.update(
        PYTHON_DOTENV_DISABLED="1",
        NEXT_TELEMETRY_DISABLED="1",
        NODE_OPTIONS="--max-old-space-size=512",
        TEMP=str(temporary),
        TMP=str(temporary),
        PIP_CONFIG_FILE=os.devnull,
        PIP_INDEX_URL="https://pypi.org/simple",
        PIP_CACHE_DIR=str(destination / "cache" / "pip"),
        npm_config_cache=str(destination / "cache" / "npm"),
        npm_config_userconfig=os.devnull,
        npm_config_registry="https://registry.npmjs.org",
    )
    return environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--install", action="store_true", help="Install fresh Python/Node dependencies; requires network and disk space.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = prepare(root, args.directory)
    destination = source.parent
    if args.install:
        environment = install_environment(destination)
        subprocess.run([sys.executable, "-m", "venv", str(destination / "venv")], env=environment, check=True)
        python = destination / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(source / "requirements-ci.txt")], cwd=source, env=environment, check=True)
        subprocess.run([str(python), "-m", "pip", "check"], cwd=source, env=environment, check=True)
        npm = shutil.which("npm", path=environment.get("PATH"))
        if not npm:
            raise SystemExit("Node/npm is required; public source and Python environment were retained.")
        subprocess.run([npm, "ci"], cwd=source / "frontend", env=environment, check=True)
    print(f"Public sandbox ready: {source}")
    print("Follow docs/SHOWCASE.md in that copy. Start only on loopback; no services were started.")


if __name__ == "__main__":
    main()
