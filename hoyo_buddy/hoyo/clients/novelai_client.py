import novelai


class NAIClient(novelai.NAIClient):
    def __init__(self, *, token: str, host_url: str, **kwargs) -> None:
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
        images = await super().generate_image(
            metadata, host=novelai.Host.CUSTOM, verbose=False, is_opus=False
        )
        im = images[0]
        return im.data
