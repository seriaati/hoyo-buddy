from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" ALTER COLUMN "game" TYPE VARCHAR(32) USING "game"::VARCHAR(32);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" ALTER COLUMN "game" TYPE VARCHAR(32) USING "game"::VARCHAR(32);"""
