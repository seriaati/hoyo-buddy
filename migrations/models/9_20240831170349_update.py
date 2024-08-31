from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "challengehistory" ADD "lang" VARCHAR(5);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "challengehistory" DROP COLUMN "lang";"""
