from pydantic import BaseModel, Field


class Config(BaseModel):
    """Plugin Config Here"""

    uninfo_cache: bool = Field(True, description="是否启用缓存")
    """是否启用缓存"""

    uninfo_cache_expire: int = Field(300, description="缓存过期时间")
    """缓存过期时间"""
