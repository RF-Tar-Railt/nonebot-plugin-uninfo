from warnings import warn

from nonebot_plugin_uninfo.constraint import SupportAdapter
from nonebot_plugin_uninfo.fetch import InfoFetcher
from nonebot_plugin_uninfo.loader import BaseLoader


class Loader(BaseLoader):
    def get_adapter(self) -> SupportAdapter:
        return SupportAdapter.gewechat

    def get_fetcher(self) -> InfoFetcher:
        from .main import fetcher

        warn("Adapter `Gewechat` is deprecated and will be removed in the future.", DeprecationWarning, stacklevel=2)
        return fetcher
