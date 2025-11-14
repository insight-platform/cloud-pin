import asyncio
import ssl
from functools import cached_property
from ssl import SSLContext
from typing import override
from urllib.parse import urlparse

from picows import WSError, ws_connect
from savant_rs.py.log import get_logger

from savant_cloudpin.cfg import ClientServiceConfig
from savant_cloudpin.services._base import PumpServiceBase
from savant_cloudpin.services._measuring import Measurements
from savant_cloudpin.services._protocol import API_KEY_HEADER

logger = get_logger(__package__ or __name__)


class ClientService(PumpServiceBase["ClientService"]):
    def __init__(self, config: ClientServiceConfig) -> None:
        super().__init__(config, Measurements("Client", config.metrics))
        ws_endpoint = config.websockets.endpoint
        scheme = urlparse(ws_endpoint).scheme
        if not config.websockets.ssl.insecure and scheme != "wss":
            raise ValueError(
                f"Invalid WebSocket URL scheme '{scheme}'. 'wss' is expected"
            )

        self._ws_endpoint = ws_endpoint
        self._ssl = config.websockets.ssl
        self._api_key = config.websockets.api_key
        self._reconnect_timeout = config.websockets.reconnect_timeout

    @cached_property
    def _ssl_context(self) -> SSLContext | None:
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ctx.check_hostname = self._ssl.check_hostname
        ctx.hostname_checks_common_name = self._ssl.check_hostname

        if self._ssl.ca_file:
            ctx.load_verify_locations(self._ssl.ca_file)
        if self._ssl.cert_file and self._ssl.key_file:
            ctx.load_cert_chain(self._ssl.cert_file, self._ssl.key_file)
        else:
            logger.warning("Continue without client certificate authentication")
        return ctx

    async def _connect(self) -> None:
        try:
            self._measurements.increment_ws_connection_attempts()

            _, listener = await ws_connect(
                ws_listener_factory=self._create_listener,
                url=self._ws_endpoint,
                ssl_context=self._ssl_context,
                extra_headers={API_KEY_HEADER: self._api_key},
            )
            if listener:
                return
        except ConnectionRefusedError, ConnectionResetError:
            self._measurements.increment_ws_connection_errors()
            await asyncio.sleep(self._io_timeout)
            return
        except ssl.SSLCertVerificationError as orig_err:
            self._measurements.increment_ws_connection_errors()
            err = ConnectionError("Error connecting WS. Certificate problems")
            raise err from orig_err
        except WSError as orig_err:
            self._measurements.increment_ws_connection_errors()
            err = ConnectionError("Error connecting WS. Maybe auth problems")
            raise err from orig_err
        except OSError:
            self._measurements.increment_ws_connection_errors()
            logger.exception(f"Fail to connect to {self._ws_endpoint}")
            return

        self._measurements.increment_ws_connection_errors()
        raise ConnectionError("Error connecting WS. Maybe auth problems")

    async def _reconnect_loop(self) -> None:
        while self.running:
            if not self._is_connected():
                logger.info("Connecting to server ...")
                await self._connect()
            await asyncio.sleep(self._reconnect_timeout)

    @override
    async def _serve(self) -> None:
        try:
            with self._zmq_src, self._zmq_sink:
                self._zmq_src.start()
                self._zmq_sink.start()

                self.started.set()

                loops = [
                    self._inbound_ws_loop,
                    self._outbound_ws_loop,
                    self._reconnect_loop,
                ]
                tasks = [asyncio.create_task(loop()) for loop in loops]
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                self.stop_running()
                await asyncio.gather(*tasks)
        finally:
            if self._connection:
                self._connection.shutdown()
