from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "autotaskresult" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "task_type" VARCHAR(20) NOT NULL,
    "success" BOOL NOT NULL,
    "completed_at" TIMESTAMPTZ NOT NULL,
    "account_id" INT NOT NULL REFERENCES "hoyoaccount" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_autotaskres_account_462643" UNIQUE ("account_id", "task_type")
);
        ALTER TABLE "cardsettings" ALTER COLUMN "custom_images" TYPE JSONB USING "custom_images"::JSONB;
        ALTER TABLE "cardsettings" ALTER COLUMN "highlight_substats" TYPE JSONB USING "highlight_substats"::JSONB;
        ALTER TABLE "challengehistory" ALTER COLUMN "json_data" TYPE JSONB USING "json_data"::JSONB;
        ALTER TABLE "discordembed" ADD "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
        ALTER TABLE "discordembed" ALTER COLUMN "data" TYPE JSONB USING "data"::JSONB;
        ALTER TABLE "farmnotify" ALTER COLUMN "item_ids" TYPE JSONB USING "item_ids"::JSONB;
        ALTER TABLE "hoyoaccount" ALTER COLUMN "redeemed_codes" TYPE JSONB USING "redeemed_codes"::JSONB;
        ALTER TABLE "jsonfile" ALTER COLUMN "data" TYPE JSONB USING "data"::JSONB;
        ALTER TABLE "leaderboard" ALTER COLUMN "extra_info" TYPE JSONB USING "extra_info"::JSONB;
        ALTER TABLE "user" ALTER COLUMN "temp_data" TYPE JSONB USING "temp_data"::JSONB;
        ALTER TABLE "user" ALTER COLUMN "dismissibles" TYPE JSONB USING "dismissibles"::JSONB;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "user" ALTER COLUMN "temp_data" TYPE JSONB USING "temp_data"::JSONB;
        ALTER TABLE "user" ALTER COLUMN "dismissibles" TYPE JSONB USING "dismissibles"::JSONB;
        ALTER TABLE "jsonfile" ALTER COLUMN "data" TYPE JSONB USING "data"::JSONB;
        ALTER TABLE "farmnotify" ALTER COLUMN "item_ids" TYPE JSONB USING "item_ids"::JSONB;
        ALTER TABLE "hoyoaccount" ALTER COLUMN "redeemed_codes" TYPE JSONB USING "redeemed_codes"::JSONB;
        ALTER TABLE "leaderboard" ALTER COLUMN "extra_info" TYPE JSONB USING "extra_info"::JSONB;
        ALTER TABLE "cardsettings" ALTER COLUMN "custom_images" TYPE JSONB USING "custom_images"::JSONB;
        ALTER TABLE "cardsettings" ALTER COLUMN "highlight_substats" TYPE JSONB USING "highlight_substats"::JSONB;
        ALTER TABLE "discordembed" DROP COLUMN "created_at";
        ALTER TABLE "discordembed" ALTER COLUMN "data" TYPE JSONB USING "data"::JSONB;
        ALTER TABLE "challengehistory" ALTER COLUMN "json_data" TYPE JSONB USING "json_data"::JSONB;
        DROP TABLE IF EXISTS "autotaskresult";"""


MODELS_STATE = (
    "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"
)
