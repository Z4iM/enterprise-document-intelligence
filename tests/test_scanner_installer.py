"""Scanner setup must fail before executing/replacing unverified tools."""

import sys
from unittest.mock import Mock

import pytest

from scripts import install_grype


def test_existing_corrupt_archive_is_rejected_without_network_or_binary_overwrite(
    tmp_path, monkeypatch
):
    name, _ = install_grype.ASSETS["Windows"]
    (tmp_path / f"grype_{install_grype.VERSION}_{name}").write_bytes(
        b"synthetic-corrupt-archive"
    )
    binary = tmp_path / "grype.exe"
    binary.write_bytes(b"preserve-existing-binary")
    monkeypatch.setattr(install_grype.platform, "system", lambda: "Windows")
    monkeypatch.setattr(install_grype.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(sys, "argv", ["install_grype", "--directory", str(tmp_path)])
    network = Mock(side_effect=AssertionError("No download should occur"))
    monkeypatch.setattr(install_grype.urllib.request, "urlopen", network)
    with pytest.raises(SystemExit, match="checksum mismatch"):
        install_grype.main()
    assert binary.read_bytes() == b"preserve-existing-binary"
    network.assert_not_called()
