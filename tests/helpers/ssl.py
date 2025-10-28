from dataclasses import dataclass
import subprocess
import sys
from os import PathLike
from pathlib import Path

SSL_DIR = Path(".cache/ssl/")


@dataclass
class CertificateAuthority:
    name: str
    cert_file: str


@dataclass
class SignedCertKey:
    ca_name: str
    ca_file: str
    cert_file: str
    key_file: str


def shell(command: str, cwd: PathLike | None = None) -> None:
    proc = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        cwd=cwd,
    )
    if proc.stdout:
        print(proc.stdout.decode())
    if proc.stderr:
        print(proc.stderr.decode(), file=sys.stderr)

    proc.check_returncode()


def prepare_ca(ca_name: str) -> CertificateAuthority:
    ca_dir = SSL_DIR / ca_name
    ca_private_dir = ca_dir / "private"
    ca_newcerts_dir = ca_dir / "newcerts"
    database_file = ca_dir / "index.txt"
    serial_file = ca_dir / "serial"
    crt_path = ca_dir / "cacert.pem"
    key_path = ca_private_dir / "cakey.pem"

    ca_dir.mkdir(parents=True, exist_ok=True)
    ca_private_dir.mkdir(parents=True, exist_ok=True)
    ca_newcerts_dir.mkdir(parents=True, exist_ok=True)
    database_file.touch(exist_ok=True)

    if not serial_file.exists():
        serial_file.write_text("01")

    if not crt_path.exists() or not key_path.exists():
        shell(
            f"openssl req -new -x509 -days 3650 -noenc -extensions v3_ca -keyout {key_path} -out {crt_path}"
            f" -subj '/CN={ca_name}/C=US/ST=California/L=San Francisco/O={ca_name}'"
            r" -addext 'keyUsage=critical,digitalSignature,keyCertSign'"
        )

    return CertificateAuthority(ca_name, str(crt_path))


def prepare_signed_cert_key(ca_name: str, filename: str) -> SignedCertKey:
    ca_dir = SSL_DIR / ca_name
    key_path = SSL_DIR / f"{filename}.key"
    csr_path = SSL_DIR / f"{filename}.csr"
    pem_path = SSL_DIR / f"{filename}.pem"
    config_path = Path(__file__).parent / "openssl.cnf"

    if not key_path.exists():
        shell(f"openssl genrsa -out {key_path} 2048")
    if not csr_path.exists():
        shell(
            f"openssl req -new -key {key_path} -out {csr_path}"
            f" -subj '/CN={filename}/C=US/ST=California/L=San Francisco/O={ca_name}'"
        )
    if not pem_path.exists():
        shell(
            f"openssl ca -batch -config {config_path}"
            f" -in {csr_path.absolute()} -out {pem_path.absolute()}",
            cwd=ca_dir,
        )

    return SignedCertKey(
        ca_name=ca_name,
        ca_file=str(ca_dir / "cacert.pem"),
        cert_file=str(pem_path),
        key_file=str(key_path),
    )
