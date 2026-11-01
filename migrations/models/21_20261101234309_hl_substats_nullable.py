from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "cardsettings" ALTER COLUMN "highlight_substats" DROP DEFAULT;
        ALTER TABLE "cardsettings" ALTER COLUMN "highlight_substats" DROP NOT NULL;
        UPDATE "cardsettings" SET "highlight_substats" = NULL WHERE "highlight_substats" = '[]'::jsonb;
        UPDATE "cardsettings" cs SET "highlight_substats" = NULL
        FROM "jsonfile" j
        WHERE j."name" = 'zzz_avatar_battle_temp.json'
            AND cs."game" = 'Zenless Zone Zero'
            AND cs."highlight_substats" IS NOT NULL
            AND (
                SELECT COALESCE(jsonb_agg(DISTINCT x ORDER BY x), '[]'::jsonb) FROM (
                    SELECT CASE v::int
                        WHEN 11103 THEN 11102 WHEN 12103 THEN 12102 WHEN 13103 THEN 13102
                        ELSE v::int END AS x
                    FROM jsonb_array_elements_text(cs."highlight_substats") v
                ) saved
            ) = (
                SELECT COALESCE(jsonb_agg(DISTINCT x ORDER BY x), '[]'::jsonb) FROM (
                    SELECT CASE v::int
                        WHEN 1 THEN 11102 WHEN 2 THEN 12102 WHEN 3 THEN 13102 WHEN 5 THEN 20103
                        WHEN 6 THEN 21103 WHEN 8 THEN 31203 WHEN 9 THEN 23203 END AS x
                    FROM jsonb_array_elements_text(COALESCE(j."data" -> cs."character_id", '[]'::jsonb)) v
                ) dflt
                WHERE x IS NOT NULL
            );"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE "cardsettings" SET "highlight_substats" = '[]'::jsonb WHERE "highlight_substats" IS NULL;
        ALTER TABLE "cardsettings" ALTER COLUMN "highlight_substats" SET DEFAULT '[]'::jsonb;
        ALTER TABLE "cardsettings" ALTER COLUMN "highlight_substats" SET NOT NULL;"""


MODELS_STATE = (
    "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"
)
