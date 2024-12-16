from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" ADD "mimo_auto_task" BOOL NOT NULL  DEFAULT True;
        ALTER TABLE "hoyoaccount" ADD "mimo_auto_buy" BOOL NOT NULL  DEFAULT False;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" DROP COLUMN "mimo_auto_task";
        ALTER TABLE "hoyoaccount" DROP COLUMN "mimo_auto_buy";"""
