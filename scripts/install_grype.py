"""Install a checksum-pinned public scanner; no shell installer or runtime dependency."""

import argparse
import hashlib
import io
import platform
import tarfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "0.121.0"
ASSETS = {
    "Windows": (
        "windows_amd64.zip",
        "f867bbdc14bd8b0d99b3fc47d839af07480a540072b16896373a8ba32b76f588",
    ),
    "Linux": (
        "linux_amd64.tar.gz",
        "64e07133d3486115de647a66581461dccf5c732748a0a3119077395565f15519",
    ),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    args = parser.parse_args()
    if platform.system() not in ASSETS or platform.machine().lower() not in {
        "amd64",
        "x86_64",
    }:
        raise SystemExit("Pinned scanner supports Windows/Linux x86_64 only.")
    name, expected = ASSETS[platform.system()]
    directory = Path(args.directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / f"grype_{VERSION}_{name}"
    if not archive.exists():
        url = f"https://github.com/anchore/grype/releases/download/v{VERSION}/{archive.name}"
        with (
            urllib.request.urlopen(url, timeout=90) as response,
            archive.open("xb") as target,
        ):
            while chunk := response.read(1024 * 1024):
                target.write(chunk)
    data = archive.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise SystemExit(
            "Scanner archive checksum mismatch; nothing executed or overwritten."
        )
    binary = "grype.exe" if platform.system() == "Windows" else "grype"
    if name.endswith("zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as package:
            content = package.read(binary)
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as package:
            content = package.extractfile(binary).read()
    target = directory / binary
    if target.exists():
        if target.read_bytes() != content:
            raise SystemExit("Existing scanner differs; refusing to overwrite.")
    else:
        target.write_bytes(content)
        target.chmod(0o755)
    print(f"Verified Grype {VERSION}: {target}")


if __name__ == "__main__":
    main()
