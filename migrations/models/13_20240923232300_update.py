from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "leaderboard" ADD "extra_info" JSONB;
        ALTER TABLE "leaderboard" ALTER COLUMN "type" TYPE VARCHAR(32) USING "type"::VARCHAR(32);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "leaderboard" DROP COLUMN "extra_info";
        ALTER TABLE "leaderboard" ALTER COLUMN "type" TYPE VARCHAR(32) USING "type"::VARCHAR(32);"""
