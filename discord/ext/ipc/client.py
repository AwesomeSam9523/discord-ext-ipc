import asyncio
import logging
import typing
import uuid

import aiohttp
from discord.ext.ipc.errors import *
from discord.ext.ipc.websocket import *

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
        self.websocket = IpcWebsocket(
            host, port, multicast_port, secret_key, resume_upon_stop
        )

    async def request(self, endpoint, **kwargs):
        """Make a request to the IPC server process.

        Parameters
        ----------
        endpoint: str
            The endpoint to request on the server
        **kwargs
            The data to send to the endpoint
        """
        if self.websocket.ws is None:
            await self.websocket._start()
        return await self.websocket.send(endpoint, kwargs)
