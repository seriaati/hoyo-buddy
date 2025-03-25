from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "challengehistory" ADD "json_data" JSONB;
        ALTER TABLE "challengehistory" ALTER COLUMN "data" DROP NOT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "challengehistory" DROP COLUMN "json_data";
        ALTER TABLE "challengehistory" ALTER COLUMN "data" SET NOT NULL;"""
