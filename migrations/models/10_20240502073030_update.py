from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" ALTER COLUMN "uid" TYPE BIGINT USING "uid"::BIGINT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" ALTER COLUMN "uid" TYPE INT USING "uid"::INT;"""
