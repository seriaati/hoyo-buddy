from collections import OrderedDict, defaultdict
from typing import Any

import aiocache


class LFUCache(aiocache.SimpleMemoryCache):
    def __init__(self, maxsize: int = 1024, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._maxsize = maxsize
        self._frequency: defaultdict[Any, int] = defaultdict(int)
        self._freq_list: OrderedDict[int, list[Any]] = OrderedDict()

    def _update_freq(self, key: Any) -> None:
        freq = self._frequency[key]
        self._frequency[key] += 1

        if freq in self._freq_list:
            self._freq_list[freq].remove(key)
            if not self._freq_list[freq]:
                del self._freq_list[freq]

        if self._frequency[key] not in self._freq_list:
            self._freq_list[self._frequency[key]] = []
        self._freq_list[self._frequency[key]].append(key)

    async def _evict(self) -> None:
        if len(self._cache) >= self._maxsize:
            min_freq = next(iter(self._freq_list))
            key_to_evict = self._freq_list[min_freq].pop(0)
            if not self._freq_list[min_freq]:
                del self._freq_list[min_freq]
            await super().delete(key_to_evict)
            del self._frequency[key_to_evict]

    async def get(self, key: Any, default: Any = None) -> Any:
        if await super().exists(key):
            self._update_freq(key)
        return await super().get(key, default)

    async def set(self, key: Any, value: Any, ttl: int = 0) -> None:
        await self._evict()
        await super().set(key, value, ttl)
        self._update_freq(key)

    async def delete(self, key: Any) -> None:
        await super().delete(key)
        del self._frequency[key]
