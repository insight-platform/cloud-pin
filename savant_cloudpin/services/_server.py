import asyncio
import ssl
from asyncio.base_events import Server
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import cached_property
from ssl import SSLContext
from typing import override
from urllib.parse import urlparse

from picows import WSListener, WSUpgradeRequest, ws_create_server
from savant_rs.py.log import get_logger

from savant_cloudpin.cfg import ServerServiceConfig
from savant_cloudpin.services._base import PumpServiceBase
from savant_cloudpin.services._measuring import Measurements
from savant_cloudpin.services._protocol import API_KEY_HEADER

logger = get_logger(__package__ or __name__)


class ServerService(PumpServiceBase["ServerService"]):
    def __init__(self, config: ServerServiceConfig) -> None:
        super().__init__(config, Measurements("Server", config.metrics))
        default_port = "443" if config.websockets.ssl else "80"
        ws_endpoint = config.websockets.endpoint
        netloc = urlparse(ws_endpoint).netloc.split(":")

        self._host = netloc.pop(0)
        self._port = int(netloc.pop() if netloc else default_port)
        self._ssl = config.websockets.ssl
        self._api_key = config.websockets.api_key

    @cached_property
    def _ssl_context(self) -> SSLContext | None:
        if not self._ssl:
            logger.warning("No SSL configured. Unsafe connection")
            return None

        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ctx.load_cert_chain(self._ssl.cert_file, self._ssl.key_file)
        if self._ssl.client_cert_required:
            ctx.verify_mode = ssl.VerifyMode.CERT_REQUIRED
            ctx.load_verify_locations(cafile=self._ssl.ca_file)
        else:
            logger.warning("Continue without client certificate authentication")
        return ctx

    def _authenticate_listener(self, request: WSUpgradeRequest) -> WSListener:
        self._measurements.increment_ws_connection_attempts()

        client_api_key = request.headers.get(API_KEY_HEADER, None)
        if self._api_key != client_api_key:
            self._measurements.increment_ws_connection_errors()
            raise ConnectionRefusedError("Invalid API key")
        return self._create_listener()

    @asynccontextmanager
    async def _create_server(self) -> AsyncGenerator[Server]:
        server = await ws_create_server(
            ws_listener_factory=self._authenticate_listener,
            host=self._host,
            port=self._port,
            ssl=self._ssl_context,
        )
        async with server:
            yield server
            server.close_clients()

    @override
    async def _serve(self) -> None:
        with self._zmq_src, self._zmq_sink:
            async with self._create_server() as server:
                self._zmq_src.start()
                self._zmq_sink.start()

                await server.start_serving()

                self.started.set()
                loops = [self._inbound_ws_loop, self._outbound_ws_loop]
                tasks = [asyncio.create_task(loop()) for loop in loops]
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                self.stop_running()
                await asyncio.gather(*tasks)
