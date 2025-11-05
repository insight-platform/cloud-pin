from typing import overload

from savant_rs.py.log import get_logger

from savant_cloudpin.cfg import ClientServiceConfig, ServerServiceConfig
from savant_cloudpin.services._client import ClientService
from savant_cloudpin.services._server import ServerService

__all__ = [
    "ClientService",
    "create_service",
    "ServerService",
]

logger = get_logger(__package__ or __name__)


@overload
def create_service(config: ClientServiceConfig) -> ClientService: ...
@overload
def create_service(config: ServerServiceConfig) -> ServerService: ...
def create_service(
    config: ClientServiceConfig | ServerServiceConfig,
) -> ClientService | ServerService:
    try:
        if isinstance(config, ServerServiceConfig):
            return ServerService(config)
        else:
            return ClientService(config)
    except:
        logger.exception("Error service configuring")
        raise
