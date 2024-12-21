from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" ADD "mimo_all_claimed_time" TIMESTAMPTZ;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" DROP COLUMN "mimo_all_claimed_time";"""
