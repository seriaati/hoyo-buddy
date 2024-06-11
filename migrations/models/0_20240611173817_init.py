from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "enkacache" (
    "uid" BIGSERIAL NOT NULL PRIMARY KEY,
    "hsr" JSONB NOT NULL,
    "genshin" JSONB NOT NULL,
    "hoyolab" JSONB NOT NULL,
    "extras" JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS "jsonfile" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "data" JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_jsonfile_name_1de105" ON "jsonfile" ("name");
CREATE TABLE IF NOT EXISTS "user" (
    "id" BIGINT NOT NULL  PRIMARY KEY,
    "temp_data" JSONB NOT NULL,
    "last_interaction" TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS "cardsettings" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "character_id" VARCHAR(8) NOT NULL,
    "dark_mode" BOOL NOT NULL,
    "custom_images" JSONB NOT NULL,
    "custom_primary_color" VARCHAR(7),
    "current_image" TEXT,
    "template" VARCHAR(32) NOT NULL  DEFAULT 'hb1',
    "user_id" BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_cardsetting_charact_fa558c" UNIQUE ("character_id", "user_id")
);
CREATE TABLE IF NOT EXISTS "hoyoaccount" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "uid" BIGINT NOT NULL,
    "username" VARCHAR(32) NOT NULL,
    "nickname" VARCHAR(32),
    "game" VARCHAR(32) NOT NULL,
    "cookies" TEXT NOT NULL,
    "server" VARCHAR(32) NOT NULL,
    "daily_checkin" BOOL NOT NULL  DEFAULT True,
    "current" BOOL NOT NULL  DEFAULT False,
    "redeemed_codes" JSONB NOT NULL,
    "auto_redeem" BOOL NOT NULL  DEFAULT True,
    "public" BOOL NOT NULL  DEFAULT True,
    "user_id" BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_hoyoaccount_uid_caad37" UNIQUE ("uid", "game", "user_id")
);
CREATE INDEX IF NOT EXISTS "idx_hoyoaccount_uid_e838aa" ON "hoyoaccount" ("uid");
COMMENT ON COLUMN "hoyoaccount"."game" IS 'GENSHIN: Genshin Impact\nSTARRAIL: Honkai: Star Rail\nHONKAI: Honkai Impact 3rd';
CREATE TABLE IF NOT EXISTS "accountnotifsettings" (
    "notify_on_checkin_failure" BOOL NOT NULL  DEFAULT True,
    "notify_on_checkin_success" BOOL NOT NULL  DEFAULT True,
    "account_id" INT NOT NULL  PRIMARY KEY REFERENCES "hoyoaccount" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "farmnotify" (
    "enabled" BOOL NOT NULL  DEFAULT True,
    "item_ids" JSONB NOT NULL,
    "account_id" INT NOT NULL  PRIMARY KEY REFERENCES "hoyoaccount" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "notesnotify" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "type" SMALLINT NOT NULL,
    "enabled" BOOL NOT NULL  DEFAULT True,
    "last_notif_time" TIMESTAMPTZ,
    "last_check_time" TIMESTAMPTZ,
    "est_time" TIMESTAMPTZ,
    "notify_interval" SMALLINT NOT NULL,
    "check_interval" SMALLINT NOT NULL,
    "max_notif_count" SMALLINT NOT NULL  DEFAULT 5,
    "current_notif_count" SMALLINT NOT NULL  DEFAULT 0,
    "threshold" SMALLINT,
    "notify_time" SMALLINT,
    "notify_weekday" SMALLINT,
    "account_id" INT NOT NULL REFERENCES "hoyoaccount" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_notesnotify_type_0526b8" UNIQUE ("type", "account_id")
);
COMMENT ON COLUMN "notesnotify"."type" IS 'RESIN: 1\nREALM_CURRENCY: 2\nTB_POWER: 3\nGI_EXPED: 4\nHSR_EXPED: 5\nPT: 6\nGI_DAILY: 7\nHSR_DAILY: 8\nRESIN_DISCOUNT: 9\nECHO_OF_WAR: 10\nRESERVED_TB_POWER: 11';
CREATE TABLE IF NOT EXISTS "settings" (
    "lang" VARCHAR(5),
    "dark_mode" BOOL NOT NULL  DEFAULT True,
    "user_id" BIGINT NOT NULL  PRIMARY KEY REFERENCES "user" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
