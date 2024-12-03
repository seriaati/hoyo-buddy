from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "customimage" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" VARCHAR(100),
    "url" TEXT,
    "character_id" VARCHAR(8) NOT NULL,
    "user_id" BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_customimage_charact_e2ae7a" UNIQUE ("character_id", "user_id", "url")
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "customimage";"""
