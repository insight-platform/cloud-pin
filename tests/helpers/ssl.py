from savant_cloudpin.cfg._models import SSLCertKeyConfig
from pathlib import Path
import subprocess
from dataclasses import dataclass


SSL_DIR = Path(".cache/ssl/")
SERVER_FILENAME = "test_server"
CLIENT_FILENAME = "test_client"
ANOTHER_SERVER_FILENAME = "test_another_server"
ANOTHER_CLIENT_FILENAME = "test_another_client"


@dataclass
class TestSSLFiles:
    server: SSLCertKeyConfig
    client: SSLCertKeyConfig
    another_server: SSLCertKeyConfig
    another_client: SSLCertKeyConfig


def ensure_self_signed_ssl(filename: str) -> SSLCertKeyConfig:
    crt_path = SSL_DIR / f"{filename}.crt"
    key_path = SSL_DIR / f"{filename}.key"
    if not crt_path.exists() or not key_path.exists():
        subprocess.run(
            "openssl req -x509 -sha256 -nodes -days 3650 -newkey rsa:2048"
            f" -subj '/CN={filename}' -keyout {key_path} -out {crt_path}",
            shell=True,
            check=True,
        )
    return SSLCertKeyConfig(str(crt_path), str(key_path))


def ensure_ssl_files() -> TestSSLFiles:
    SSL_DIR.mkdir(parents=True, exist_ok=True)

    return TestSSLFiles(
        server=ensure_self_signed_ssl(SERVER_FILENAME),
        client=ensure_self_signed_ssl(CLIENT_FILENAME),
        another_server=ensure_self_signed_ssl(ANOTHER_SERVER_FILENAME),
        another_client=ensure_self_signed_ssl(ANOTHER_CLIENT_FILENAME),
    )
