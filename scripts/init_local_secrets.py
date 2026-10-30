"""Generate local Compose credentials only when missing; never print or overwrite them."""

import secrets
from pathlib import Path


def main():
    project = Path(__file__).resolve().parents[1]
    root = project / ".local" / "container"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not root.resolve().is_relative_to(project.resolve()):
        raise RuntimeError("Secret directory must stay in this project.")
    root.chmod(0o700)
    for name in ("postgres-password", "app-password"):
        target = root / name
        if target.is_symlink() or (target.exists() and target.stat().st_nlink > 1):
            raise RuntimeError("Secret files cannot be links.")
        try:
            with target.open("x", encoding="utf-8") as output:
                output.write(secrets.token_urlsafe(48))
        except FileExistsError:
            pass
        # Compose file secrets are bind mounts; non-root service users must be able
        # to read the file. Host traversal is protected by the 0700 parent directory.
        target.chmod(0o444)
    print("Local container secrets are ready; existing files were preserved.")


if __name__ == "__main__":
    main()
