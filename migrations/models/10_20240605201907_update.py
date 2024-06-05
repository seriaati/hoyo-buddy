from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "cardsettings" ALTER COLUMN "current_image" TYPE TEXT USING "current_image"::TEXT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "cardsettings" ALTER COLUMN "current_image" TYPE VARCHAR(100) USING "current_image"::VARCHAR(100);"""
