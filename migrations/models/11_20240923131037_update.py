from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "challengehistory" ALTER COLUMN "challenge_type" TYPE VARCHAR(32) USING "challenge_type"::VARCHAR(32);
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
COMMENT ON COLUMN "gachahistory"."game" IS 'GENSHIN: Genshin Impact
STARRAIL: Honkai: Star Rail
HONKAI: Honkai Impact 3rd
ZZZ: Zenless Zone Zero
TOT: Tears of Themis';
        CREATE TABLE IF NOT EXISTS "gachastats" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "account_id" INT NOT NULL,
    "lifetime_pulls" INT NOT NULL,
    "avg_5star_pulls" DOUBLE PRECISION NOT NULL,
    "avg_4star_pulls" DOUBLE PRECISION NOT NULL,
    "win_rate" DOUBLE PRECISION NOT NULL,
    "game" VARCHAR(32) NOT NULL,
    "banner_type" INT NOT NULL,
    CONSTRAINT "uid_gachastats_account_7c0c6d" UNIQUE ("account_id", "banner_type", "game")
);
COMMENT ON COLUMN "gachastats"."game" IS 'GENSHIN: Genshin Impact
STARRAIL: Honkai: Star Rail
HONKAI: Honkai Impact 3rd
ZZZ: Zenless Zone Zero
TOT: Tears of Themis';
        CREATE TABLE IF NOT EXISTS "leaderboard" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "type" VARCHAR(32) NOT NULL,
    "game" VARCHAR(32) NOT NULL,
    "value" DOUBLE PRECISION NOT NULL,
    "uid" BIGINT NOT NULL,
    "rank" INT NOT NULL,
    "username" VARCHAR(32) NOT NULL,
    CONSTRAINT "uid_leaderboard_type_58f2b6" UNIQUE ("type", "game", "uid")
);
COMMENT ON COLUMN "leaderboard"."type" IS 'ACHIEVEMENT: achievement';
COMMENT ON COLUMN "leaderboard"."game" IS 'GENSHIN: Genshin Impact
STARRAIL: Honkai: Star Rail
HONKAI: Honkai Impact 3rd
ZZZ: Zenless Zone Zero
TOT: Tears of Themis';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "challengehistory" ALTER COLUMN "challenge_type" TYPE VARCHAR(32) USING "challenge_type"::VARCHAR(32);
        DROP TABLE IF EXISTS "commandmetric";
        DROP TABLE IF EXISTS "gachahistory";
        DROP TABLE IF EXISTS "gachastats";
        DROP TABLE IF EXISTS "leaderboard";"""


MODELS_STATE = (
    "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"
)
