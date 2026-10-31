"""Public-source rehearsal must not export user state or overwrite existing work."""

import json
import os
import subprocess

import pytest

from scripts.prepare_showcase import install_environment, prepare


def repository(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text(".env\ndata/\n")
    (root / "README.md").write_text("Synthetic public source\n")
    (root / ".env.example").write_text("LLM_PROVIDER=disabled\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    # An empty initial commit avoids depending on the developer's Git identity.
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.test", "commit", "-qm", "synthetic"], check=True)
    return root


def test_export_omits_private_and_unrelated_untracked_files_and_retains_hashes(tmp_path):
    root = repository(tmp_path)
    (root / ".env").write_text("synthetic-private-marker")
    (root / "personal-notes.md").write_text("synthetic-private-marker")
    (root / "data").mkdir()
    (root / "data" / "synthetic.db").write_bytes(b"not-a-real-database")
    destination = tmp_path / "rehearsal"
    source = prepare(root, destination)
    assert (source / "README.md").is_file() and (source / ".env.example").is_file()
    assert not any((source / name).exists() for name in [".env", "data", "personal-notes.md", ".git"])
    manifest = json.loads((destination / "source-manifest.json").read_text())
    assert set(manifest["files_sha256"]) == {"README.md", ".gitignore", ".env.example"}
    with pytest.raises(ValueError, match="nonexistent"):
        prepare(root, destination)
    with pytest.raises(ValueError, match="outside"):
        prepare(root, root / "nested")


@pytest.mark.parametrize("name", [".env", ".ENV", ".npmrc"])
def test_tracked_private_file_fails_closed_before_export(tmp_path, name):
    root = repository(tmp_path)
    (root / name).write_text("synthetic-private-marker")
    subprocess.run(["git", "-C", str(root), "add", "-f", name], check=True)
    destination = tmp_path / "rejected"
    with pytest.raises(ValueError, match="non-public"):
        prepare(root, destination)
    assert not destination.exists()


def test_tracked_hard_link_cannot_export_private_content(tmp_path):
    root = repository(tmp_path)
    private = root / ".env"
    private.write_text("synthetic-private-marker")
    os.link(private, root / "public.py")
    subprocess.run(["git", "-C", str(root), "add", "public.py"], check=True)
    with pytest.raises(ValueError, match="ordinary repository file"):
        prepare(root, tmp_path / "rejected-link")


def test_install_drops_provider_and_private_package_registry_environment(tmp_path, monkeypatch):
    for key in ["GEMINI_API_KEY", "GROQ_API_KEY", "LLM_API_KEY", "PIP_EXTRA_INDEX_URL", "NODE_AUTH_TOKEN", "PYTHONPATH"]:
        monkeypatch.setenv(key, "synthetic-private-marker")
    environment = install_environment(tmp_path)
    assert "synthetic-private-marker" not in str(environment)
    assert environment["PYTHON_DOTENV_DISABLED"] == "1"
