import asyncio
import logging
import typing
import uuid

import aiohttp
from discord.ext.ipc.errors import *

log = logging.getLogger(__name__)


class Client:
    """
    Handles webserver side requests to the bot process.

    Parameters
    ----------
    host: str
        The IP or host of the IPC server, defaults to localhost
    port: int
        The port of the IPC server. If not supplied the port will be found automatically, defaults to None
    secret_key: Union[str, bytes]
        The secret key for your IPC server. Must match the server secret_key or requests will not go ahead, defaults to None
    """

    def __init__(
        self,
        host="localhost",
        port=None,
        multicast_port=20000,
        secret_key=None,
        resume_upon_stop=False
    ):
        """Constructor"""
        self.loop = asyncio.get_event_loop()
        self.secret_key = secret_key

        self.host = host
        self.port = port
        self.resume_upon_stop = resume_upon_stop

        self.session = None

        self.websocket = None
        self.multicast = None

        self.listeners = {}

        self.multicast_port = multicast_port
        self._handler_attached = False

    @property
    def url(self):
        return "ws://{0.host}:{1}".format(self, self.port if self.port else self.multicast_port)
    
    async def _websocket_handler(self):
        '''
        Handles and dispatches the websocket response.
        '''
        while True:
            recv = await self.websocket.receive()

            if recv.type == aiohttp.WSMsgType.PING:
                log.info("Received request to PING")
                await self.websocket.ping()

            elif recv.type == aiohttp.WSMsgType.PONG:
                log.info("Received PONG")

            elif recv.type == aiohttp.WSMsgType.CLOSED:
                log.error(
                    "WebSocket connection unexpectedly closed. IPC Server is unreachable. Attempting reconnection in 5 seconds."
                )

                await self.session.close()
                await asyncio.sleep(5)
                await self.init_sock()
            else:
                await self.dispatch(recv)
    
    def get_response(self, endpoint, kwargs, check=None, timeout=60):
        _uuid = str(uuid.uuid4())
        payload = {
            "endpoint": endpoint,
            "data": kwargs,
            "_uuid": _uuid,
            "headers": {"Authorization": self.secret_key},
        }
        log.debug("Client > %r", payload)
        self.loop.create_task(self.websocket.send_json(payload))

        future = self.loop.create_future()
        self.listeners[_uuid] = (check, future)
        return asyncio.wait_for(future, timeout, loop=self.loop)
    
    async def dispatch(self, data: dict):
        uuid = data.get('uuid')
        if uuid is None:
            raise RuntimeError('UUID is missing.')
        
        for key, val in self.listeners.items():
            if key == uuid:
                check: typing.Callable = val[0]
                future: asyncio.Future = val[1]

                def _check(*args):
                    return True

                if check is None:
                    check = _check
                
                if check(data):
                    future.set_result(data)
                else:
                    future.set_exception(
                        RuntimeError(f'Check failed for UUID {uuid}')
                    )

    async def init_sock(self):
        """Attempts to connect to the server

        Returns
        -------
        :class:`~aiohttp.ClientWebSocketResponse`
            The websocket connection to the server
        """
        log.info("Initiating WebSocket connection.")
        self.session = aiohttp.ClientSession()

        if not self.port:
            log.debug(
                "No port was provided - initiating multicast connection at %s.",
                self.url,
            )
            self.multicast = await self.session.ws_connect(self.url, autoping=False)

            payload = {"connect": True, "headers": {"Authorization": self.secret_key}}
            log.debug("Multicast Server < %r", payload)
            await self.multicast.send_json(payload)
            recv = await self.multicast.receive()

            log.debug("Multicast Server > %r", recv)
            if recv.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
                log.error(
                    "WebSocket connection unexpectedly closed. Multicast Server is unreachable."
                )
                raise NotConnected("Multicast server connection failed.")

            port_data = recv.json()
            self.port = port_data["port"]

        self.websocket = await self.session.ws_connect(self.url, autoping=False, autoclose=False)
        log.info("Client connected to %s", self.url)
        if not self._handler_attached:
            self.loop.create_task(self._websocket_handler())

        return self.websocket

    async def request(self, endpoint, **kwargs):
        """Make a request to the IPC server process.

        Parameters
        ----------
        endpoint: str
            The endpoint to request on the server
        **kwargs
            The data to send to the endpoint
        """
        log.info("Requesting IPC Server for %r with %r", endpoint, kwargs)
        if not self.session:
            await self.init_sock()
        if not self.websocket or (
            self.websocket.closed and self.resume_upon_stop
        ):
            await self.init_sock()

        recv = await self.get_response(endpoint, kwargs)
        log.debug("Client < %r", recv)

        return recv.json()
