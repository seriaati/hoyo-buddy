async def upgrade(db) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "cardsettings" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "character_id" VARCHAR(8) NOT NULL,
    "dark_mode" BOOL NOT NULL,
    "custom_images" JSONB NOT NULL,
    "custom_primary_color" VARCHAR(7),
    "current_image" VARCHAR(100),
    "user_id" BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_cardsetting_charact_fa558c" UNIQUE ("character_id", "user_id")
);"""


async def downgrade(db) -> str:
    return """
        DROP TABLE IF EXISTS "cardsettings";"""
