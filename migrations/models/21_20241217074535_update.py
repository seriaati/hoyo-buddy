from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


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


MODELS_STATE = (
    "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"
    "zhU12E97BG9fv/OHdXhw=="
)
