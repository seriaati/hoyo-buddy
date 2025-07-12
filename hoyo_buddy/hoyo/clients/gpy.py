from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, overload

import enka
import genshin
import hakushin
import orjson
from loguru import logger
from tortoise import Tortoise

from hoyo_buddy import models
from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import (
    AMBR_TRAVELER_ID_TO_ENKA_TRAVELER_ID,
    AMBR_UI_URL,
    DMG_BONUS_IDS,
    ELEMENT_TO_BONUS_PROP_ID,
    GPY_PATH_TO_EKNA_PATH,
    HB_GAME_TO_GPY_GAME,
    LOCALE_TO_GPY_LANG,
    PLAYER_BOY_GACHA_ART,
    PLAYER_GIRL_GACHA_ART,
    POST_REPLIES,
    contains_traveler_id,
    convert_fight_prop,
)
from hoyo_buddy.db import HoyoAccount, JSONFile
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Game, GenshinElement, Locale
from hoyo_buddy.exceptions import HoyoBuddyError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import sleep

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


class MimoClaimTaksResult(NamedTuple):
    finished: list[genshin.models.MimoTask]
    claimed_points: int
    all_claimed: bool


class ProxyGenshinClient(genshin.Client):
    def __init__(
        self,
        *args: Any,
        region: genshin.Region = genshin.Region.OVERSEAS,
        use_proxy: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            *args,
            debug=True,
            cache=genshin.SQLiteCache(static_ttl=3600 * 24 * 31),
            region=region,
            proxy=CONFIG.proxy if region is genshin.Region.OVERSEAS and use_proxy else None,
            **kwargs,
        )
        self._use_proxy = use_proxy

    @property
    def use_proxy(self) -> bool:
        return self._use_proxy

    @use_proxy.setter
    def use_proxy(self, value: bool) -> None:
        if CONFIG.proxy is None:
            logger.warning("Proxy is not set in the config, setting use_proxy will have no effect.")

        if value and self.region is genshin.Region.OVERSEAS:
            self.proxy = CONFIG.proxy
        else:
            self.proxy = None
        self._use_proxy = value


class GenshinClient(ProxyGenshinClient):
    def __init__(self, account: HoyoAccount) -> None:
        game = HB_GAME_TO_GPY_GAME[account.game]

        super().__init__(
            account.cookies,
            game=game,
            uid=account.uid,
            region=account.region,
            device_id=account.device_id,
            device_fp=account.device_fp,
            use_proxy=False,
        )
        self._account = account

    def set_lang(self, locale: Locale) -> None:
        if self._account.game is Game.STARRAIL and locale is Locale.turkish:
            self.lang = "en-us"
            return

        self.lang = (
            "zh-cn"
            if self.region is genshin.Region.CHINESE
            else LOCALE_TO_GPY_LANG.get(locale, "en-us")
        )

    def get_daily_reward_embed(
        self, daily_reward: genshin.models.DailyReward, locale: Locale, *, blur: bool
    ) -> DefaultEmbed:
        return (
            DefaultEmbed(
                locale,
                title=LocaleStr(key="reward_claimed_title"),
                description=f"{daily_reward.name} x{daily_reward.amount}",
            )
            .set_thumbnail(url=daily_reward.icon)
            .add_acc_info(self._account, blur=blur)
            .set_footer(text=LocaleStr(key="checkin_reward_embed_footer"))
        )

    @staticmethod
    def _convert_character_id_to_enka_format(character_id: str) -> str:
        """Convert character ID to the format used by EnkaAPI."""
        return (
            AMBR_TRAVELER_ID_TO_ENKA_TRAVELER_ID[character_id]
            if contains_traveler_id(character_id)
            else character_id
        )

    async def update_pc_icons(self) -> dict[str, str]:
        fields = await self.get_lineup_fields(use_cache=False)
        pc_icons = {str(character.id): character.pc_icon for character in fields.characters}
        await JSONFile.write("pc_icons.json", pc_icons)
        return pc_icons

    @staticmethod
    async def convert_gi_character(
        character: genshin.models.GenshinDetailCharacter,
    ) -> models.HoyolabGICharacter:
        """Convert GenshinDetailCharacter from gpy to HoyolabGICharacter that's used for drawing cards."""
        weapon = models.HoyolabGIWeapon(
            name=character.weapon.name,
            icon=character.weapon.icon,
            refinement=character.weapon.refinement,
            level=character.weapon.level,
            max_level=hakushin.utils.get_max_level_from_ascension(
                character.weapon.ascension, hakushin.Game.GI
            ),
            rarity=character.weapon.rarity,
            stats=[
                models.HoyolabGIStat(
                    type=convert_fight_prop(character.weapon.main_stat.info.type),
                    formatted_value=character.weapon.main_stat.final,
                )
            ],
        )
        if character.weapon.sub_stat is not None:
            weapon.stats.append(
                models.HoyolabGIStat(
                    type=convert_fight_prop(character.weapon.sub_stat.info.type),
                    formatted_value=character.weapon.sub_stat.final,
                )
            )

        constellations = [
            models.HoyolabGIConst(icon=const.icon, unlocked=const.activated)
            for const in character.constellations
        ]

        artifacts = [
            models.HoyolabGIArtifact(
                icon=artifact.icon,
                rarity=artifact.rarity,
                level=artifact.level,
                main_stat=models.HoyolabGIStat(
                    type=convert_fight_prop(artifact.main_stat.info.type),
                    formatted_value=artifact.main_stat.value,
                ),
                sub_stats=[
                    models.HoyolabGIStat(
                        type=convert_fight_prop(sub_stat.info.type), formatted_value=sub_stat.value
                    )
                    for sub_stat in artifact.sub_stats
                ],
                pos=artifact.pos,
            )
            for artifact in character.artifacts
        ]

        highest_dmg_bonus_stat = None
        for prop in character.selected_properties:
            if prop.info.type in DMG_BONUS_IDS:
                highest_dmg_bonus_stat = models.HoyolabGIStat(
                    type=convert_fight_prop(prop.info.type), formatted_value=prop.final
                )
            break
        if highest_dmg_bonus_stat is None:
            prop_id = ELEMENT_TO_BONUS_PROP_ID[
                GenshinElement.ANEMO
                if character.element == "None"
                else GenshinElement(character.element)
            ]
            prop = next(
                (prop for prop in character.element_properties if prop.info.type == prop_id), None
            )
            if prop is None:
                msg = f"Couldn't find the highest damage bonus stat for {character.name} ({character.element})"
                raise ValueError(msg)

            highest_dmg_bonus_stat = models.HoyolabGIStat(
                type=convert_fight_prop(prop_id), formatted_value=prop.final
            )

        costume: models.HoyolabGICostume | None = None
        async with enka.GenshinClient() as client:
            if character.costumes:
                costumes: dict[str, dict[str, Any]] | None = client._assets.character_data[
                    str(character.id)
                ].get("Costumes")
                if costumes:
                    chara_costume = character.costumes[0]
                    costume_data = costumes.get(str(chara_costume.id))
                    if costume_data:
                        costume = models.HoyolabGICostume(
                            icon=models.HoyolabGICharacterIcon(
                                gacha=AMBR_UI_URL.format(filename=costume_data["art"])
                            )
                        )
            talent_order = client._assets.character_data[str(character.id)]["SkillOrder"]

        if "10000005" in str(character.id):  # PlayerBoy
            gacha_art = PLAYER_BOY_GACHA_ART
        elif "10000007" in str(character.id):  # PlayerGirl
            gacha_art = PLAYER_GIRL_GACHA_ART
        else:
            gacha_art = character.gacha_art

        icon = models.HoyolabGICharacterIcon(gacha=gacha_art)

        return models.HoyolabGICharacter(
            id=character.id,
            name=character.name,
            element=GenshinElement(character.element),
            highest_dmg_bonus_stat=highest_dmg_bonus_stat,
            stats={
                convert_fight_prop(prop.info.type): models.HoyolabGIStat(
                    type=convert_fight_prop(prop.info.type), formatted_value=prop.final
                )
                for prop in character.selected_properties
            },
            rarity=character.rarity,
            weapon=weapon,
            constellations=constellations,
            talent_order=talent_order,
            talents=[
                models.HoyolabGITalent(icon=talent.icon, level=talent.level, id=talent.id)
                for talent in character.skills
            ],
            artifacts=artifacts,
            friendship_level=character.friendship,
            level=character.level,
            max_level=hakushin.utils.get_max_level_from_ascension(
                hakushin.utils.get_ascension_from_level(
                    character.level, ascended=True, game=hakushin.Game.GI
                ),
                hakushin.Game.GI,
            ),
            icon=icon,
            costume=costume,
        )

    @staticmethod
    def convert_hsr_character(
        c: genshin.models.StarRailDetailCharacter,
        property_info: dict[str, genshin.models.PropertyInfo],
    ) -> models.HoyolabHSRCharacter:
        """Convert StarRailDetailCharacter from gpy to HoyolabHSRCharacter that's used for drawing cards."""
        prop_icons: dict[int, str] = {
            prop.property_type: prop.icon for prop in property_info.values()
        }

        light_cone = (
            models.LightCone(
                id=c.equip.id,
                level=c.equip.level,
                superimpose=c.equip.rank,
                name=c.equip.name,
                max_level=hakushin.utils.get_max_level_from_ascension(
                    hakushin.utils.get_ascension_from_level(
                        c.equip.level, ascended=True, game=hakushin.Game.HSR
                    ),
                    hakushin.Game.HSR,
                ),
                rarity=c.equip.rarity,
            )
            if c.equip is not None
            else None
        )
        relics = [
            models.Relic(
                id=relic.id,
                level=relic.level,
                rarity=relic.rarity,
                icon=relic.icon,
                main_stat=models.Stat(
                    type=relic.main_property.property_type,
                    icon=prop_icons[relic.main_property.property_type],
                    formatted_value=relic.main_property.value,
                ),
                sub_stats=[
                    models.Stat(
                        type=sub_property.property_type,
                        icon=prop_icons[sub_property.property_type],
                        formatted_value=sub_property.value,
                    )
                    for sub_property in relic.properties
                ],
                type=enka.hsr.RelicType(relic.pos),
            )
            for relic in list(c.relics) + list(c.ornaments)
        ]
        return models.HoyolabHSRCharacter(
            id=str(c.id),
            element=c.element,
            name=c.name,
            level=c.level,
            eidolons_unlocked=c.rank,
            rarity=c.rarity,
            light_cone=light_cone,
            relics=relics,
            stats=[
                models.Stat(
                    icon=prop_icons[prop.property_type],
                    formatted_value=prop.final,
                    type=prop.property_type,
                )
                for prop in c.properties
            ],
            traces=[
                models.Trace(anchor=skill.anchor, icon=skill.item_url, level=skill.level)
                for skill in c.skills
            ],
            eidolons=[
                models.Eidolon(icon=eidolon.icon, unlocked=eidolon.is_unlocked)
                for eidolon in c.ranks
            ],
            max_level=hakushin.utils.get_max_level_from_ascension(
                hakushin.utils.get_ascension_from_level(
                    c.level, ascended=True, game=hakushin.Game.HSR
                ),
                hakushin.Game.HSR,
            ),
            path=GPY_PATH_TO_EKNA_PATH[c.path],
        )

    async def get_hoyolab_gi_characters(self) -> list[models.HoyolabGICharacter]:
        """Get Genshin Impact detailed characters in HoyolabGI format."""
        data = await self.get_genshin_detailed_characters(self._account.uid)
        return [await self.convert_gi_character(chara) for chara in data.characters]

    async def get_hoyolab_hsr_characters(self) -> list[models.HoyolabHSRCharacter]:
        """Get characters in HoyolabHSR format."""
        data = await self.get_starrail_characters(self.uid)
        return [
            self.convert_hsr_character(chara, dict(data.property_info))
            for chara in data.avatar_list
        ]

    async def get_zzz_agents(
        self, uid: int | None = None
    ) -> Sequence[genshin.models.ZZZPartialAgent]:
        return await super().get_zzz_agents(uid)

    async def update_cookie_token(self) -> None:
        """Update the cookie token."""
        parsed_cookies = self._account.dict_cookies
        cookies = await genshin.fetch_cookie_with_stoken_v2(parsed_cookies, token_types=[2, 4])
        parsed_cookies.update(cookies)
        self.set_cookies(parsed_cookies)
        new_str_cookies = "; ".join(f"{k}={v}" for k, v in parsed_cookies.items())

        self._account.cookies = new_str_cookies
        await self._account.save(update_fields=("cookies",))

    async def redeem_codes(
        self, codes: Sequence[str], *, locale: Locale, blur: bool = True, skip_redeemed: bool = True
    ) -> DefaultEmbed | None:
        """Redeem multiple codes and return an embed with the results."""
        if not codes:
            return None

        results: list[tuple[str, str, bool]] = []
        for code in codes:
            if not code or (
                code.capitalize() in {c.capitalize() for c in self._account.redeemed_codes}
                and skip_redeemed
            ):
                continue

            msg, success = await self.redeem_code(code.strip(), locale=locale)
            results.append((code, msg, success))
            await sleep("redeem")

        if not results:
            return None
        return self.get_redeem_codes_embed(results, locale=locale, blur=blur)

    def get_redeem_codes_embed(
        self, results: list[tuple[str, str, bool]], *, locale: Locale, blur: bool
    ) -> DefaultEmbed:
        # get the first 25 results
        results = results[:25]
        embed = DefaultEmbed(
            locale, title=LocaleStr(key="redeem_command_embed.title")
        ).add_acc_info(self._account, blur=blur)
        for result in results:
            name = f"{'✅' if result[2] else '❌'} {result[0]}"
            embed.add_field(name=name, value=result[1])

        return embed

    async def _add_to_redeemed_codes(self, code: str) -> None:
        await Tortoise.get_connection("default").execute_query(
            "UPDATE hoyoaccount SET redeemed_codes = CASE WHEN NOT redeemed_codes @> $2::jsonb THEN redeemed_codes || $2::jsonb ELSE redeemed_codes END WHERE id = $1;",
            [self._account.id, orjson.dumps(code).decode()],
        )

    @staticmethod
    def _handle_redeem_error(e: Exception, locale: Locale) -> str:
        embed, _ = get_error_embed(e, locale)

        assert embed.title is not None
        if embed.description is None:
            return embed.title
        if "HoYo API Error" in embed.title:
            return embed.description
        return f"{embed.title}\n{embed.description}"

    async def redeem_code(self, code: str, *, locale: Locale) -> tuple[str, bool]:
        """Redeem a code, return a message and a boolean indicating success."""
        success = False

        try:
            if code in self._account.redeemed_codes:
                raise genshin.RedemptionClaimed

            await super().redeem_code(code)
        except genshin.InvalidCookies:
            # cookie token is invalid
            if "stoken" in self._account.dict_cookies and "ltmid_v2" in self._account.dict_cookies:
                # cookie token can be refreshed
                try:
                    await self.update_cookie_token()
                except genshin.InvalidCookies:
                    # cookie token refresh failed
                    msg = self._handle_redeem_error(
                        genshin.GenshinException({"retcode": 1000}), locale
                    )
                else:
                    # cookie token refresh succeeded, redeem code again
                    await sleep("redeem")
                    return await self.redeem_code(code, locale=locale)
            else:
                # cookie token can't be refreshed
                msg = self._handle_redeem_error(genshin.GenshinException({"retcode": 999}), locale)
        except genshin.RedemptionCooldown:
            # sleep then retry
            await sleep("redeem")
            return await self.redeem_code(code, locale=locale)
        except Exception as e:
            if isinstance(e, genshin.RedemptionClaimed | genshin.RedemptionInvalid):
                await self._add_to_redeemed_codes(code)

            msg = self._handle_redeem_error(e, locale)
        else:
            await self._add_to_redeemed_codes(code)
            success = True
            msg = LocaleStr(key="redeem_code.success").translate(locale)

        return msg, success

    async def update_cookies_for_checkin(self) -> dict[str, str] | None:
        """Update client cookies for check-in if the client region is CN."""
        if self.region is genshin.Region.OVERSEAS:
            return None

        cookies = self._account.dict_cookies
        if "stoken" not in cookies or "mid" not in cookies:
            return None

        cookie_token = (await genshin.cn_fetch_cookie_token_with_stoken_v2(cookies))["cookie_token"]
        cookies["cookie_token"] = cookie_token
        cookies["account_id"] = cookies["ltuid"]
        self.set_cookies(cookies)
        return cookies

    async def request_daily_reward(
        self,
        endpoint: str,
        *,
        game: genshin.Game | None = None,
        method: str = "GET",
        lang: str | None = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        challenge: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> Mapping[str, str]:
        """Claim the daily reward."""
        await self.update_cookies_for_checkin()
        return await super().request_daily_reward(
            endpoint,
            game=game,
            method=method,
            lang=lang,
            params=params,
            headers=headers,
            challenge=challenge,
            **kwargs,
        )

    @overload
    async def get_notes_(self, game: Literal[genshin.Game.GENSHIN]) -> genshin.models.Notes: ...

    @overload
    async def get_notes_(
        self, game: Literal[genshin.Game.STARRAIL]
    ) -> genshin.models.StarRailNote: ...

    @overload
    async def get_notes_(self, game: Literal[genshin.Game.ZZZ]) -> genshin.models.ZZZNotes: ...

    @overload
    async def get_notes_(
        self, game: Literal[genshin.Game.HONKAI]
    ) -> genshin.models.HonkaiNotes: ...

    async def get_notes_(
        self,
        game: Literal[
            genshin.Game.GENSHIN, genshin.Game.STARRAIL, genshin.Game.ZZZ, genshin.Game.HONKAI
        ],
    ) -> (
        genshin.models.Notes
        | genshin.models.StarRailNote
        | genshin.models.ZZZNotes
        | genshin.models.HonkaiNotes
    ):
        uid = self._account.uid

        if game is genshin.Game.GENSHIN:
            return await super().get_genshin_notes(uid)
        if game is genshin.Game.STARRAIL:
            return await super().get_starrail_notes(uid)
        if game is genshin.Game.ZZZ:
            return await super().get_zzz_notes(uid)
        if game is genshin.Game.HONKAI:
            return await super().get_honkai_notes(uid)

    async def get_genshin_notes(self) -> genshin.models.Notes:
        return await self.get_notes_(genshin.Game.GENSHIN)

    async def get_starrail_notes(self) -> genshin.models.StarRailNote:
        return await self.get_notes_(genshin.Game.STARRAIL)

    async def get_zzz_notes(self) -> genshin.models.ZZZNotes:
        return await self.get_notes_(genshin.Game.ZZZ)

    async def get_honkai_notes(self) -> genshin.models.HonkaiNotes:
        return await self.get_notes_(genshin.Game.HONKAI)

    async def get_mimo_tasks(
        self, *, game_id: int, version_id: int
    ) -> Sequence[genshin.models.MimoTask]:
        try:
            return await super().get_mimo_tasks(game_id=game_id, version_id=version_id)
        except genshin.GenshinException as e:
            if e.retcode == -510001:  # Invalid fields in calculation
                raise HoyoBuddyError(
                    message=LocaleStr(
                        key="gi_mimo_start_desc",
                        url="https://act.hoyolab.com/ys/event/bbs-event-20240828mimo/index.html",
                    )
                ) from e
            raise

    async def finish_and_claim_mimo_tasks(
        self, *, game_id: int, version_id: int
    ) -> MimoClaimTaksResult:
        finished_tasks: list[genshin.models.MimoTask] = []
        finished = False  # True if at least one task was finished
        claimed_points = 0

        tasks = await self.get_mimo_tasks(game_id=game_id, version_id=version_id)

        for task in tasks:
            if task.status is not genshin.models.MimoTaskStatus.ONGOING:
                continue

            if task.type in {
                genshin.models.MimoTaskType.FINISHABLE,
                genshin.models.MimoTaskType.TRAILER,
                genshin.models.MimoTaskType.VISIT,
                genshin.models.MimoTaskType.VIEW_TOPIC,
            }:
                try:
                    await self.finish_mimo_task(task.id, game_id=game_id, version_id=version_id)
                    await sleep("mimo_task")
                except genshin.GenshinException as e:
                    if e.retcode == -500001:  # Invalid fields in calculation
                        continue
                    raise
                finished = True

            elif task.type is genshin.models.MimoTaskType.COMMENT:
                url_data = orjson.loads(task.jump_url)
                args: dict[str, str] | None = url_data.get("args")
                if args is None:
                    continue

                post_id: str | None = args.get("post_id")
                if post_id is not None:
                    try:
                        reply_id = await self.reply_to_post(
                            random.choice(POST_REPLIES), post_id=int(post_id)
                        )
                    except genshin.AccountMuted:
                        await sleep("mimo_comment")
                    else:
                        await sleep("mimo_comment")
                        await self.delete_reply(reply_id=reply_id, post_id=int(post_id))
                        await sleep("mimo_comment")
                    finished = True

                topic_id: str | None = args.get("topic_id")
                if topic_id is not None:
                    await self.join_topic(int(topic_id))
                    await sleep("mimo_comment")
                    await self.leave_topic(int(topic_id))
                    await sleep("mimo_comment")
                    finished = True

        if finished:
            tasks = await self.get_mimo_tasks(game_id=game_id, version_id=version_id)

        for task in tasks:
            if task.status is genshin.models.MimoTaskStatus.FINISHED:
                try:
                    await self.claim_mimo_task_reward(
                        task.id, game_id=game_id, version_id=version_id
                    )
                    await sleep("mimo_task")
                except genshin.GenshinException as e:
                    if e.retcode == -500001:  # Invalid fields in calculation
                        continue
                    raise

                finished_tasks.append(task)
                claimed_points += task.point

        return MimoClaimTaksResult(
            finished_tasks,
            claimed_points,
            all(task.status is genshin.models.MimoTaskStatus.CLAIMED for task in tasks),
        )

    async def buy_mimo_valuables(
        self, *, game_id: int, version_id: int
    ) -> list[tuple[genshin.models.MimoShopItem, str]]:
        result: list[tuple[genshin.models.MimoShopItem, str]] = []
        bought: list[tuple[int, str]] = []

        original_lang = self.lang[:]
        points = await self.get_mimo_point_count()
        await sleep("mimo_shop")

        self.lang = "en-us"
        en_items = await self.get_mimo_shop_items(game_id=game_id, version_id=version_id)
        await sleep("mimo_shop")

        # Sort items from most expensive to least expensive
        en_items = sorted(en_items, key=lambda item: item.cost, reverse=True)

        keywords = ("Stellar Jades", "Polychrome")
        for item in en_items:
            if (
                any(keyword in item.name for keyword in keywords)
                and item.status is genshin.models.MimoShopItemStatus.EXCHANGEABLE
                and item.cost <= points
            ):
                try:
                    code = await self.buy_mimo_shop_item(
                        item.id, game_id=game_id, version_id=version_id
                    )
                    await sleep("mimo_shop")
                except genshin.GenshinException as e:
                    if e.retcode == -502005:  # Insufficient points
                        continue
                    raise

                bought.append((item.id, code))
                points -= item.cost

        if bought:
            self.lang = original_lang
            if original_lang != "en-us":
                items = await self.get_mimo_shop_items(game_id=game_id, version_id=version_id)
            else:
                items = en_items

            item_mi18n = {item.id: item for item in items}
            result = [(item_mi18n[item_id], code) for item_id, code in bought]

        return result
