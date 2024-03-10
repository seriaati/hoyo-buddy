async def upgrade(db) -> str:
    return """
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
COMMENT ON COLUMN "notesnotify"."type" IS 'RESIN: 1\nREALM_CURRENCY: 2\nTB_POWER: 3\nGI_EXPED: 4\nHSR_EXPED: 5\nPT: 6\nGI_DAILY: 7\nHSR_DAILY: 8\nRESIN_DISCOUNT: 9\nECHO_OF_WAR: 10\nRESERVED_TB_POWER: 11';"""


async def downgrade(db) -> str:
    return """
        DROP TABLE IF EXISTS "notesnotify";"""
