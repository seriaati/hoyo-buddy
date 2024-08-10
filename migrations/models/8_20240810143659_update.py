from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "settings" ADD "enable_dyk" BOOL NOT NULL  DEFAULT True;
        ALTER TABLE "settings" ALTER COLUMN "zzz_card_temp" SET DEFAULT 'hb2';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "settings" DROP COLUMN "enable_dyk";
        ALTER TABLE "settings" ALTER COLUMN "zzz_card_temp" SET DEFAULT 'hb1';"""
