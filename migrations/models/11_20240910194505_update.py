from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "commandmetric" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" VARCHAR(32) NOT NULL,
    "count" INT NOT NULL,
    "last_time" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP
);
        CREATE TABLE IF NOT EXISTS "gachahistory" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "wish_id" BIGINT NOT NULL,
    "rarity" INT NOT NULL,
    "time" TIMESTAMPTZ NOT NULL,
    "item_id" INT NOT NULL,
    "banner_type" INT NOT NULL,
    "num" INT NOT NULL,
    "num_since_last" INT NOT NULL,
    "game" VARCHAR(32) NOT NULL,
    "account_id" INT NOT NULL REFERENCES "hoyoaccount" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_gachahistor_wish_id_4585cf" UNIQUE ("wish_id", "game")
);
CREATE INDEX IF NOT EXISTS "idx_gachahistor_account_41d59c" ON "gachahistory" ("account_id");
COMMENT ON COLUMN "gachahistory"."game" IS 'GENSHIN: Genshin Impact\nSTARRAIL: Honkai: Star Rail\nHONKAI: Honkai Impact 3rd\nZZZ: Zenless Zone Zero\nTOT: Tears of Themis';
        CREATE TABLE IF NOT EXISTS "gachastats" (
    "account_id" INT NOT NULL  PRIMARY KEY,
    "lifetime_pulls" INT NOT NULL,
    "avg_5star_pulls" DOUBLE PRECISION NOT NULL,
    "avg_4star_pulls" DOUBLE PRECISION NOT NULL,
    "win_rate" DOUBLE PRECISION NOT NULL,
    "game" VARCHAR(32) NOT NULL
);
COMMENT ON COLUMN "gachastats"."game" IS 'GENSHIN: Genshin Impact\nSTARRAIL: Honkai: Star Rail\nHONKAI: Honkai Impact 3rd\nZZZ: Zenless Zone Zero\nTOT: Tears of Themis';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "commandmetric";
        DROP TABLE IF EXISTS "gachahistory";
        DROP TABLE IF EXISTS "gachastats";"""
