from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "dmchannel" (
    "id" BIGINT NOT NULL PRIMARY KEY,
    "user_id" BIGINT NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "dmchannel";"""
