async def upgrade(db) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "farmnotify" (
    "enabled" BOOL NOT NULL  DEFAULT True,
    "item_ids" JSONB NOT NULL,
    "account_id" INT NOT NULL  PRIMARY KEY REFERENCES "hoyoaccount" ("id") ON DELETE CASCADE
);"""


async def downgrade(db) -> str:
    return """
        DROP TABLE IF EXISTS "farmnotify";"""
