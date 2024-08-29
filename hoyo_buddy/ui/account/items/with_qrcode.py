from __future__ import annotations

import asyncio
import io
from typing import TYPE_CHECKING, Any

import discord
import genshin
import qrcode
import qrcode.image.pil

from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Platform

from ...components import Button, GoBackButton

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager  # noqa: F401


class WithQRCode(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(label="通过扫描二维码")

    @property
    def _instructions_embed(self) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="指引",
            description="使用米游社扫描下方二维码来登录",
        )
        embed.set_image(url="attachment://qrcode.webp")
        return embed

    @property
    def _scanned_embed(self) -> DefaultEmbed:
        return DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="指引",
            description="扫码成功, 请在装备上同意登录。",
        )

    @property
    def _confirmed_embed(self) -> DefaultEmbed:
        return DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="指引",
            description="登录成功",
        )

    @staticmethod
    async def _fetch_cookies(raw_data: genshin.models.QRCodeRawData) -> dict[str, Any]:
        cookie_token = await genshin.fetch_cookie_token_with_game_token(
            game_token=raw_data.game_token, account_id=raw_data.account_id,
        )
        stoken = await genshin.fetch_stoken_with_game_token(
            game_token=raw_data.game_token, account_id=int(raw_data.account_id),
        )

        return {
            "stoken_v2": stoken.token,
            "ltuid": stoken.aid,
            "account_id": stoken.aid,
            "ltmid": stoken.mid,
            "cookie_token": cookie_token,
        }

    async def callback(self, i: Interaction) -> Any:
        await self.set_loading_state(i)

        client = genshin.Client(
            region=genshin.Region.CHINESE,  # OS doesn't have QR code login
            game=genshin.Game.GENSHIN,
        )
        result = await client._create_qrcode()
        qrcode_img: qrcode.image.pil.PilImage = qrcode.make(result.url)

        fp = io.BytesIO()
        qrcode_img.save(fp, format="WEBP", lossless=True)
        fp.seek(0)
        file_ = discord.File(fp, filename="qrcode.webp")

        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(go_back_button)

        await self.unset_loading_state(i, embed=self._instructions_embed, attachments=[file_])

        scanned = False
        while True:
            try:
                check_result = await client._check_qrcode(
                    result.app_id, result.device_id, result.ticket,
                )
            except genshin.GenshinException as e:
                if e.retcode == -106:
                    # QR code expired
                    return await i.edit_original_response(
                        embed=DefaultEmbed(
                            self.view.locale,
                            self.view.translator,
                            title="二维码已过期",
                            description="请刷新二维码后重试",
                        ),
                        attachments=[],
                    )
                raise
            if check_result.status is genshin.models.QRCodeStatus.SCANNED and not scanned:
                await i.edit_original_response(embed=self._scanned_embed, attachments=[])
                scanned = True
            elif check_result.status is genshin.models.QRCodeStatus.CONFIRMED:
                await i.edit_original_response(embed=self._confirmed_embed, attachments=[])
                break

            await asyncio.sleep(2.0)

        assert check_result.payload.raw is not None
        cookies = await self._fetch_cookies(check_result.payload.raw)
        await self.view.finish_cookie_setup(cookies, platform=Platform.MIYOUSHE, interaction=i)
        return None
