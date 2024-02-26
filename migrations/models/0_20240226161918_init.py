async def upgrade(db) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "user" (
    "id" BIGINT NOT NULL  PRIMARY KEY,
    "temp_data" JSON NOT NULL
);
CREATE TABLE IF NOT EXISTS "hoyoaccount" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "uid" INT NOT NULL,
    "username" VARCHAR(32) NOT NULL,
    "nickname" VARCHAR(32),
    "game" VARCHAR(32) NOT NULL  /* GENSHIN: Genshin Impact\nSTARRAIL: Honkai: Star Rail\nHONKAI: Honkai Impact 3rd */,
    "cookies" TEXT NOT NULL,
    "server" VARCHAR(32) NOT NULL,
    "daily_checkin" INT NOT NULL  DEFAULT 1,
    "user_id" BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_hoyoaccount_uid_caad37" UNIQUE ("uid", "game", "user_id")
);
CREATE INDEX IF NOT EXISTS "idx_hoyoaccount_uid_e838aa" ON "hoyoaccount" ("uid");
CREATE TABLE IF NOT EXISTS "accountnotifsettings" (
    "notify_on_checkin_failure" INT NOT NULL  DEFAULT 1,
    "notify_on_checkin_success" INT NOT NULL  DEFAULT 1,
    "account_id" INT NOT NULL  PRIMARY KEY REFERENCES "hoyoaccount" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "settings" (
    "lang" VARCHAR(5),
    "dark_mode" INT NOT NULL  DEFAULT 1,
    "user_id" BIGINT NOT NULL  PRIMARY KEY REFERENCES "user" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSON NOT NULL
);"""


async def downgrade(db) -> str:
    return """
        """
