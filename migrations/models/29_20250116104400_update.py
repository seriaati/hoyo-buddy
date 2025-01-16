from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "settings" ALTER COLUMN "lang" TYPE VARCHAR(10) USING "lang"::VARCHAR(10);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "settings" ALTER COLUMN "lang" TYPE VARCHAR(5) USING "lang"::VARCHAR(5);"""
