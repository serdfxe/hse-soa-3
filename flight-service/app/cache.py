import json
import logging
from typing import Optional

from redis.asyncio.sentinel import Sentinel

from app.config import settings

logger = logging.getLogger(__name__)


def _parse_sentinel_hosts(hosts_str: str) -> list[tuple[str, int]]:
    """Parse comma-separated 'host:port' string into list of (host, port) tuples."""
    result = []
    for entry in hosts_str.split(","):
        entry = entry.strip()
        if ":" in entry:
            host, port_str = entry.rsplit(":", 1)
            result.append((host.strip(), int(port_str.strip())))
        else:
            result.append((entry, 26379))
    return result


class RedisCache:
    def __init__(self):
        sentinels = _parse_sentinel_hosts(settings.redis_sentinel_hosts)
        self._sentinel = Sentinel(
            sentinels,
            sentinel_kwargs={"password": settings.redis_password} if settings.redis_password else {},
            password=settings.redis_password if settings.redis_password else None,
        )
        self._master_name = settings.redis_master_name
        self._ttl = settings.cache_ttl

    def _master(self):
        return self._sentinel.master_for(
            self._master_name,
            password=settings.redis_password if settings.redis_password else None,
        )

    # ---------- Flight cache ----------

    def _flight_key(self, flight_id: int) -> str:
        return f"flight:{flight_id}"

    async def get_flight(self, flight_id: int) -> Optional[dict]:
        try:
            client = self._master()
            data = await client.get(self._flight_key(flight_id))
            if data:
                logger.info(f"Cache HIT: flight:{flight_id}")
                return json.loads(data)
            logger.info(f"Cache MISS: flight:{flight_id}")
            return None
        except Exception as e:
            logger.warning(f"Redis get_flight error: {e}")
            return None

    async def set_flight(self, flight_id: int, data: dict) -> None:
        try:
            client = self._master()
            await client.set(self._flight_key(flight_id), json.dumps(data), ex=self._ttl)
        except Exception as e:
            logger.warning(f"Redis set_flight error: {e}")

    async def delete_flight(self, flight_id: int) -> None:
        try:
            client = self._master()
            await client.delete(self._flight_key(flight_id))
        except Exception as e:
            logger.warning(f"Redis delete_flight error: {e}")

    # ---------- Search cache ----------

    def _search_key(self, origin: str, destination: str, date: str) -> str:
        return f"search:{origin}:{destination}:{date}"

    async def get_search(self, origin: str, destination: str, date: str) -> Optional[list]:
        try:
            client = self._master()
            key = self._search_key(origin, destination, date)
            data = await client.get(key)
            if data:
                logger.info(f"Cache HIT: {key}")
                return json.loads(data)
            logger.info(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.warning(f"Redis get_search error: {e}")
            return None

    async def set_search(self, origin: str, destination: str, date: str, data: list) -> None:
        try:
            client = self._master()
            key = self._search_key(origin, destination, date)
            await client.set(key, json.dumps(data), ex=self._ttl)
        except Exception as e:
            logger.warning(f"Redis set_search error: {e}")

    async def delete_search(self, origin: str, destination: str, date: str) -> None:
        try:
            client = self._master()
            key = self._search_key(origin, destination, date)
            await client.delete(key)
        except Exception as e:
            logger.warning(f"Redis delete_search error: {e}")


# Singleton instance
cache = RedisCache()
