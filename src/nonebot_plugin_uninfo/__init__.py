from nonebot.plugin import PluginMetadata

from .config import Config
from .constraint import SupportAdapter as SupportAdapter
from .constraint import SupportAdapterModule
from .constraint import SupportScope as SupportScope
from .fetch import InfoFetcher as InfoFetcher
from .model import Member as Member
from .model import MuteInfo as MuteInfo
from .model import Role as Role
from .model import Scene as Scene
from .model import SceneType as SceneType
from .model import Session as Session
from .model import User as User
from .params import Interface as Interface
from .params import QryItrface as QryItrface
from .params import QueryInterface as QueryInterface
from .params import UniSession as UniSession
from .params import Uninfo as Uninfo
from .params import get_interface as get_interface
from .params import get_session as get_session
from .permission import ADMIN as ADMIN
from .permission import GROUP as GROUP
from .permission import GUILD as GUILD
from .permission import MEMBER as MEMBER
from .permission import OWNER as OWNER
from .permission import PRIVATE as PRIVATE
from .permission import ROLE_IN as ROLE_IN
from .permission import ROLE_LEVEL as ROLE_LEVEL
from .permission import ROLE_NOT_IN as ROLE_NOT_IN
from .permission import SCENE_IN as SCENE_IN
from .permission import SCENE_NOT_IN as SCENE_NOT_IN
from .permission import USER_IN as USER_IN
from .permission import USER_NOT_IN as USER_NOT_IN

__plugin_meta__ = PluginMetadata(
    name="通用信息",
    description="多平台的会话信息(用户、群组、频道)获取插件",
    usage="session_info: Uninfo",
    type="library",
    config=Config,
    homepage="https://github.com/RF-Tar-Railt/nonebot-plugin-uninfo",
    supported_adapters=set(SupportAdapterModule.__members__.values()),
)
