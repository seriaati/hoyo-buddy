async def upgrade(db) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "cardsettings" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "character_id" VARCHAR(8) NOT NULL,
    "dark_mode" INT NOT NULL,
    "custom_images" JSON NOT NULL,
    "custom_primary_color" VARCHAR(7),
    "user_id" BIGINT NOT NULL UNIQUE REFERENCES "user" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_cardsetting_charact_fa558c" UNIQUE ("character_id", "user_id")
);"""


async def downgrade(db) -> str:
    return """
        DROP TABLE IF EXISTS "cardsettings";"""
