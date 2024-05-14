from __future__ import annotations


async def upgrade(db) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "user" (
    "id" BIGINT NOT NULL  PRIMARY KEY,
    "temp_data" JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS "hoyoaccount" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "uid" INT NOT NULL,
    "username" VARCHAR(32) NOT NULL,
    "nickname" VARCHAR(32),
    "game" VARCHAR(32) NOT NULL,
    "cookies" TEXT NOT NULL,
    "server" VARCHAR(32) NOT NULL,
    "daily_checkin" BOOL NOT NULL  DEFAULT True,
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


async def downgrade() -> str:
    return """
        """
