from __future__ import annotations

from typing import Any

import novelai
import novelai.exceptions

from ...exceptions import AIGenImageError


class NAIClient(novelai.NAIClient):
    def __init__(self, *, token: str, host_url: str, **kwargs: Any) -> None:
        novelai.Host.CUSTOM.value.url = host_url
        super().__init__(token=token, **kwargs)

    async def generate_image(self, prompt: str, negative_prompt: str) -> bytes:
        metadata = novelai.Metadata(
            prompt=prompt,
            negative_prompt=negative_prompt,
            res_preset=novelai.Resolution.NORMAL_PORTRAIT,
            steps=28,
            n_samples=1,
        )
        try:
            images = await super().generate_image(
                metadata, host=novelai.Host.CUSTOM, verbose=False, is_opus=False
            )
        except novelai.exceptions.NovelAIError as e:
            raise AIGenImageError from e

        im = images[0]
        return im.data
