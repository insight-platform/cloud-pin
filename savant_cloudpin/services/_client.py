import asyncio
import ssl
from functools import cached_property
from ssl import SSLContext
from typing import override
from urllib.parse import urlparse

from picows import WSError, ws_connect

from savant_cloudpin.cfg import ClientServiceConfig
from savant_cloudpin.services._base import PumpServiceBase
from savant_cloudpin.services._protocol import API_KEY_HEADER


class ClientService(PumpServiceBase["ClientService"]):
    def __init__(self, config: ClientServiceConfig) -> None:
        super().__init__(config)
        ws_url = config.websockets.server_url
        scheme = urlparse(ws_url).scheme
        if scheme != "wss":
            raise ValueError(
                f"Invalid WebSocket URL scheme '{scheme}'. 'wss' is expected"
            )

        self._server_url = ws_url
        self._ssl = config.websockets.ssl
        self._api_key = config.websockets.api_key

    @cached_property
    def _ssl_context(self) -> SSLContext | None:
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ctx.load_verify_locations(self._ssl.ca_file)
        ctx.check_hostname = self._ssl.check_hostname
        ctx.hostname_checks_common_name = self._ssl.check_hostname

        if self._ssl.cert_file and self._ssl.key_file:
            ctx.load_cert_chain(self._ssl.cert_file, self._ssl.key_file)
        return ctx

    async def _connect(self) -> None:
        try:
            _, listener = await ws_connect(
                ws_listener_factory=self._create_listener,
                url=self._server_url,
                ssl_context=self._ssl_context,
                extra_headers={API_KEY_HEADER: self._api_key},
            )
            if not listener:
                raise ConnectionError("Error connecting WS. Maybe auth problems")
        except ConnectionRefusedError, ConnectionResetError:
            await asyncio.sleep(self._io_timeout)
            return
        except ssl.SSLCertVerificationError as orig_err:
            err = ConnectionError("Error connecting WS. Certificate plroblems")
            raise err from orig_err
        except WSError as orig_err:
            err = ConnectionError("Error connecting WS. Maybe auth problems")
            raise err from orig_err

    async def _reconnect_loop(self) -> None:
        while self.running:
            if not self._is_connected():
                await self._connect()
            await asyncio.sleep(self._io_timeout)

    @override
    async def _serve(self) -> None:
        try:
            with self._source, self._sink:
                self._source.start()
                self._sink.start()

                self.started.set()
                await asyncio.gather(
                    self._inbound_ws_loop(),
                    self._outbound_ws_loop(),
                    self._reconnect_loop(),
                )
        finally:
            if self._connection:
                self._connection.shutdown()
