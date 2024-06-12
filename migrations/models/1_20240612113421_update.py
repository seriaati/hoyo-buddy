from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" ADD "device_fp" VARCHAR(13);
        ALTER TABLE "hoyoaccount" ADD "device_id" VARCHAR(36);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" DROP COLUMN "device_fp";
        ALTER TABLE "hoyoaccount" DROP COLUMN "device_id";"""
