import aiohttp
import logging
import asyncio
import uuid

log = logging.getLogger(__name__)

class IpcWebsocket():
    def __init__(
        self,
        host='localhost',
        port = None,
        multicast_port = 20000,
        secret_key=None,
        resume_upon_stop=False
    ):
        self.ws = None
        self.session = None

        self.host = host
        self.port = port
        self.multicast_port = multicast_port
        self.secret_key = secret_key
        self.resume_upon_stop = resume_upon_stop

        self.listeners = {}
        self._task = None
    
    @property
    def url(self):
        '''
        Returns the websocket url.
        '''
        return 'ws://{0}:{1}'.format(self.host, self.port if self.port else self.multicast_port)
    
    def get_response(self, _uuid, loop, check=None, timeout=60):
        future = loop.create_future()
        self.listeners[_uuid] = (check, future)
        return asyncio.wait_for(future, timeout, loop=loop)
    
    async def _start(self):
        '''
        Starts the websocket. This is an internal method and you shouldn't call it anywhere.
        '''
        if self.ws is not None:
            raise RuntimeError(
                'WebSocket already running...'
            )

        if self.session is not None:
            await self.session.close()
        self.session = aiohttp.ClientSession()

        if not self.port:
            log.debug(
                'No port was provided - initiating multicast connection at %s.',
                self.url,
            )
            self.multicast = await self.session.ws_connect(self.url, autoping=False)

            payload = {'connect': True, 'headers': {'Authorization': self.secret_key}}
            log.debug('Multicast Server < %r', payload)
            await self.multicast.send_json(payload)
            recv = await self.multicast.receive()

            log.debug('Multicast Server > %r', recv)
            if recv.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
                log.error(
                    'WebSocket connection unexpectedly closed. Multicast Server is unreachable.'
                )
                raise RuntimeError(
                    'Multicast server connection failed.'
                )

            port_data = recv.json()
            self.port = port_data['port']

        self.ws = await self.session.ws_connect(self.url, autoping=False, autoclose=False)
        if self._task:
            self._task.cancel()

        self._task = asyncio.ensure_future(self._websocket_handler())

        log.info('Client connected to %s', self.url)
    
    async def _websocket_handler(self):
        '''
        Handles and dispatches the websocket response.
        '''
        log.info('WS Handler Online!')
        while True:
            if self.ws.closed:
                break
            recv = await self.ws.receive()
            log.debug('WS Msg: %r', recv)
            if recv.type == aiohttp.WSMsgType.PING:
                log.info('Received request to PING')
                await self.ws.ping()

            elif recv.type == aiohttp.WSMsgType.PONG:
                log.info('Received PONG')

            elif recv.type == aiohttp.WSMsgType.CLOSED:
                log.error(
                    'WebSocket connection unexpectedly closed. IPC Server is unreachable. Attempting reconnection in 5 seconds.'
                )

                await asyncio.sleep(5)
                self.ws = None
                await self._start()
                break
            else:
                json = recv.json()
                log.debug('Dispatching %r', json)
                await self._dispatch(json)
    
    async def _dispatch(self, data: dict):
        '''
        Dispatches a websocket response.
        '''
        log.debug('Dispatch -> %r', data)
        _uuid = data.get('_uuid')
        if _uuid is None:
            raise RuntimeError('UUID is missing.')
        
        log.debug('Listeners: %r', self.listeners)
        for key, val in self.listeners.items():
            if key == _uuid:
                check = val[0]
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

    async def send(
        self,
        endpoint: str,
        kwargs: dict
    ):
        log.info("Requesting IPC Server for %r with %r", endpoint, kwargs)
        
        _uuid = str(uuid.uuid4())
        payload = {
            "endpoint": endpoint,
            "data": kwargs,
            "_uuid": _uuid,
            "headers": {"Authorization": self.secret_key},
        }
        log.debug("Client > %r", payload)

        await self.ws.send_json(payload)
        recv = await self.get_response(_uuid, asyncio.get_running_loop())

        log.debug("Client < %r", recv)
        return recv['data']
