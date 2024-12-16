from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "accountnotifsettings" ADD "mimo_task_success" BOOL NOT NULL  DEFAULT True;
        ALTER TABLE "accountnotifsettings" ADD "mimo_task_failure" BOOL NOT NULL  DEFAULT True;
        ALTER TABLE "accountnotifsettings" ADD "mimo_buy_success" BOOL NOT NULL  DEFAULT True;
        ALTER TABLE "accountnotifsettings" ADD "mimo_buy_failure" BOOL NOT NULL  DEFAULT True;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "accountnotifsettings" DROP COLUMN "mimo_task_success";
        ALTER TABLE "accountnotifsettings" DROP COLUMN "mimo_task_failure";
        ALTER TABLE "accountnotifsettings" DROP COLUMN "mimo_buy_success";
        ALTER TABLE "accountnotifsettings" DROP COLUMN "mimo_buy_failure";"""
