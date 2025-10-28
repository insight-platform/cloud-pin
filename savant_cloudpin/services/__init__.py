from savant_cloudpin.cfg import ClientServiceConfig, ServerServiceConfig
from savant_cloudpin.services._client import ClientService
from savant_cloudpin.services._server import ServerService

__all__ = [
    "ClientService",
    "create_service",
    "ServerService",
]


def create_service(
    config: ClientServiceConfig | ServerServiceConfig,
) -> ClientService | ServerService:
    if isinstance(config, ServerServiceConfig):
        return ServerService(config)
    else:
        return ClientService(config)
