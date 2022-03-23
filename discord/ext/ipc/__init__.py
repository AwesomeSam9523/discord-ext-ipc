import collections
import imp

from discord.ext.ipc.client import Client
from discord.ext.ipc.server import Server
from discord.ext.ipc.slient import Slient
from discord.ext.ipc.errors import *


_VersionInfo = collections.namedtuple("_VersionInfo", "major minor micro release serial")

version = "2.1.2"
version_info = _VersionInfo(2, 1, 2, "final", 0)
