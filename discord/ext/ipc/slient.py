'''
Credits: BlackThunder#4007
Source: https://github.com/BlackThunder01001/discord-ext-ipc/blob/main/discord/ext/ipc/slient.py
'''

from .client import Client
from .server import Server

class Slient(Client, Server):
    """
    Merges the methods of class:`.Client` & class:`.Server` to allow intercommunication
    between two discord bots. 
    """
    def __init__(
        self,
        bot,
        host="localhost",
        base_port = 8654,
        secret_key = None,
        base_multicast = 20000,
        instance = 0
    ):
        self.client = Client(
            port = base_port + instance,
            multicast_port = base_multicast +1-instance,
            host = host,
            secret_key = secret_key)

        self.server = Server(
            bot = bot,
            port = base_port+1-instance,
            multicast_port = base_multicast + instance,
            host = host,
            secret_key = secret_key
        )
        for com in (self.server, self.client):
            for method in dir(com):
                if not method.startswith('__'):
                    try:
                        setattr(self, method, getattr(com, method))
                    except:
                        pass
