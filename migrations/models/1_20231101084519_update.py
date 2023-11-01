from tortoise.backends.base.client import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "settings" ADD "dark_mode" INT NOT NULL  DEFAULT 1;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "settings" DROP COLUMN "dark_mode";"""
