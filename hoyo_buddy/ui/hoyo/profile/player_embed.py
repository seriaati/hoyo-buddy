from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.l10n import LevelStr, LocaleStr
from hoyo_buddy.utils.misc import blur_uid

if TYPE_CHECKING:
    import enka
    import genshin

    from hoyo_buddy.db.models.hoyo_account import HoyoAccount


class PlayerEmbedMixin:
    starrail_data: enka.hsr.ShowcaseResponse | None
    genshin_data: enka.gi.ShowcaseResponse | None
    zzz_data: enka.zzz.ShowcaseResponse | None

    hoyolab_hsr_user: genshin.models.StarRailUserStats | None
    hoyolab_gi_user: genshin.models.PartialGenshinUserStats | None
    hoyolab_zzz_user: genshin.models.RecordCard | None

    uid: int
    locale: Locale
    _account: HoyoAccount | None

    @property
    def uid_str(self) -> str:
        return blur_uid(self.uid) if self._account is not None else str(self.uid)

    @property
    def default(self) -> DefaultEmbed:
        return DefaultEmbed(
            self.locale,
            title=LocaleStr(key="profile.no_data.title"),
            description=LocaleStr(key="profile.no_data.description"),
        )

    @property
    def enka_hsr(self) -> DefaultEmbed | None:
        if self.starrail_data is None:
            return None

        player = self.starrail_data.player
        embed = DefaultEmbed(
            self.locale,
            title=f"{player.nickname} ({self.uid_str})",
            description=LocaleStr(
                key="profile.player_info.embed.description",
                level=player.level,
                world_level=player.equilibrium_level,
                friend_count=player.friend_count,
                light_cones=player.stats.light_cone_count,
                characters=player.stats.character_count,
                achievements=player.stats.achievement_count,
            ),
        )
        embed.set_thumbnail(url=player.icon)
        if player.signature:
            embed.set_footer(text=player.signature)
        return embed

    @property
    def enka_gi(self) -> DefaultEmbed | None:
        if self.genshin_data is None:
            return None

        player = self.genshin_data.player
        embed = DefaultEmbed(self.locale, title=f"{player.nickname} ({self.uid_str})")

        embed.add_field(name=LocaleStr(key="profile_gi_embed_ar"), value=str(player.level))
        embed.add_field(
            name=LocaleStr(key="profile_gi_embed_world_level"), value=str(player.world_level)
        )
        embed.add_field(
            name=LocaleStr(key="achievement_complete_count", mi18n_game=Game.GENSHIN),
            value=str(player.achievements),
        )
        embed.add_field(
            name=LocaleStr(key="full_fetter_avatar_num", mi18n_game=Game.GENSHIN),
            value=str(player.max_friendship_character_count),
        )
        embed.add_field(
            name=LocaleStr(key="spriral_abyss", mi18n_game=Game.GENSHIN),
            value=f"{player.abyss_floor}-{player.abyss_level}",
        )
        if player.theater_act is not None:
            embed.add_field(
                name=LocaleStr(key="card_role_combat_name", mi18n_game=Game.GENSHIN),
                value=LocaleStr(
                    key="card_role_combat_value", mi18n_game=Game.GENSHIN, x=player.theater_act
                ),
            )

        embed.set_thumbnail(url=player.profile_picture_icon.circle)
        embed.set_image(url=player.namecard.full)
        if player.signature:
            embed.set_footer(text=player.signature)

        return embed

    @property
    def enka_zzz(self) -> DefaultEmbed | None:
        if self.zzz_data is None:
            return None

        player = self.zzz_data.player

        stand_medal = next((medal for medal in player.medals if medal.type == 4), None)
        assault_medal = next((medal for medal in player.medals if medal.type == 3), None)
        tower_medal = next((medal for medal in player.medals if medal.type == 2), None)
        shiyu_medal = next((medal for medal in player.medals if medal.type == 1), None)

        embed = DefaultEmbed(
            self.locale,
            title=f"{player.nickname} ({self.uid_str})",
            description=LevelStr(player.level),
        )
        embed.set_author(name=player.title.text)

        embed.add_field(
            name=LocaleStr(key="climbing_tower_layer_s2", mi18n_game=Game.ZZZ),
            value=str(stand_medal.value) if stand_medal is not None else "0",
        )
        embed.add_field(
            name=LocaleStr(key="memory_battlefield", mi18n_game=Game.ZZZ),
            value=str(assault_medal.value) if assault_medal is not None else "0",
        )
        embed.add_field(
            name=LocaleStr(key="challenge-review", mi18n_game=Game.ZZZ),
            value=str(shiyu_medal.value) if shiyu_medal is not None else "0",
        )
        embed.add_field(
            name=LocaleStr(key="climbing_tower_layer", mi18n_game=Game.ZZZ),
            value=str(tower_medal.value) if tower_medal is not None else "0",
        )

        embed.set_thumbnail(url=player.avatar)
        embed.set_image(url=player.namecard.icon)

        if player.signature:
            embed.set_footer(text=player.signature)

        return embed

    @property
    def hoyolab_gi(self) -> DefaultEmbed | None:
        if self.hoyolab_gi_user is None:
            return None

        player = self.hoyolab_gi_user.info
        stats = self.hoyolab_gi_user.stats
        embed = DefaultEmbed(self.locale, title=f"{player.nickname} ({self.uid_str})")

        embed.add_field(name=LocaleStr(key="profile_gi_embed_ar"), value=str(player.level))
        embed.add_field(
            name=LocaleStr(key="achievement_complete_count", mi18n_game=Game.GENSHIN),
            value=str(stats.achievements),
        )
        embed.add_field(
            name=LocaleStr(key="full_fetter_avatar_num", mi18n_game=Game.GENSHIN),
            value=str(stats.max_friendship_characters),
        )
        embed.add_field(
            name=LocaleStr(key="spriral_abyss", mi18n_game=Game.GENSHIN), value=stats.spiral_abyss
        )
        if stats.theater.has_data:
            embed.add_field(
                name=LocaleStr(key="card_role_combat_name", mi18n_game=Game.GENSHIN),
                value=LocaleStr(
                    key="card_role_combat_value", mi18n_game=Game.GENSHIN, x=stats.theater.max_act
                ),
            )
        if stats.stygian.has_data:
            embed.add_field(
                name=LocaleStr(key="hard_challenge_block_title", mi18n_game=Game.GENSHIN),
                value=str(stats.stygian.difficulty),
            )

        embed.set_thumbnail(url=player.in_game_avatar)

    @property
    def hoyolab_hsr(self) -> DefaultEmbed | None:
        if self.hoyolab_hsr_user is None:
            return None

        player = self.hoyolab_hsr_user.info
        stats = self.hoyolab_hsr_user.stats
        return DefaultEmbed(
            self.locale,
            title=f"{player.nickname} ({self.uid_str})",
            description=LocaleStr(
                key="profile.player_info.hoyolab.embed.description",
                level=player.level,
                characters=stats.avatar_num,
                chest=stats.chest_num,
                moc=stats.abyss_process,
                achievements=stats.achievement_num,
            ),
        )

    @property
    def hoyolab_zzz(self) -> DefaultEmbed | None:
        if self.hoyolab_zzz_user is None:
            return None

        player = self.hoyolab_zzz_user
        data_str = "\n".join(f"{data.name}: {data.value}" for data in player.data)
        level_str = LevelStr(player.level).translate(self.locale)
        return DefaultEmbed(
            self.locale,
            title=f"{player.nickname} ({self.uid_str})",
            description=f"{level_str}\n{data_str}",
        )

    @property
    def player_embed(self) -> DefaultEmbed:
        return (
            # Genshin
            self.enka_gi
            or self.hoyolab_gi
            # HSR
            or self.enka_hsr
            or self.hoyolab_hsr
            # ZZZ
            or self.enka_zzz
            or self.hoyolab_zzz
            # Fallback
            or self.default
        )
