from tortoise.backends.base.client import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" RENAME COLUMN "daily_check_in" TO "daily_checkin";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" RENAME COLUMN "daily_checkin" TO "daily_check_in";"""
