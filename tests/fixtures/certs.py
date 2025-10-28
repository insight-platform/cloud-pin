import pytest

from savant_cloudpin.cfg import ClientSSLConfig, ServerSSLConfig
from tests import helpers
from tests.helpers.ssl import CertificateAuthority, SignedCertKey


@pytest.fixture
def ca() -> CertificateAuthority:
    return helpers.ssl.prepare_ca("ca")


@pytest.fixture
def another_ca() -> CertificateAuthority:
    return helpers.ssl.prepare_ca("another_ca")


@pytest.fixture
def client_cert(ca: CertificateAuthority) -> SignedCertKey:
    return helpers.ssl.prepare_signed_cert_key(ca.name, "client_signed_cert")


@pytest.fixture
def server_cert(ca: CertificateAuthority) -> SignedCertKey:
    return helpers.ssl.prepare_signed_cert_key(ca.name, "server_signed_cert")


@pytest.fixture
def another_cert(another_ca: CertificateAuthority) -> SignedCertKey:
    return helpers.ssl.prepare_signed_cert_key(another_ca.name, "another_signed_cert")


@pytest.fixture
def client_ssl_config(client_cert: SignedCertKey) -> ClientSSLConfig:
    return ClientSSLConfig(
        ca_file=client_cert.ca_file,
        cert_file=client_cert.cert_file,
        key_file=client_cert.key_file,
        check_hostname=False,
    )


@pytest.fixture
def server_ssl_config(client_cert: SignedCertKey) -> ServerSSLConfig:
    return ServerSSLConfig(
        ca_file=client_cert.ca_file,
        cert_file=client_cert.cert_file,
        key_file=client_cert.key_file,
        client_cert_required=True,
    )
