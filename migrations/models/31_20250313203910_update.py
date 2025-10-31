from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "accountnotifsettings" ADD "redeem_failure" BOOL NOT NULL DEFAULT True;
        ALTER TABLE "accountnotifsettings" ADD "redeem_success" BOOL NOT NULL DEFAULT True;
        CREATE TABLE IF NOT EXISTS "discordembed" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "data" JSONB NOT NULL,
    "task_type" VARCHAR(20) NOT NULL,
    "type" VARCHAR(7) NOT NULL,
    "account_id" INT NOT NULL REFERENCES "hoyoaccount" ("id") ON DELETE CASCADE,
    "user_id" BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "accountnotifsettings" DROP COLUMN "redeem_failure";
        ALTER TABLE "accountnotifsettings" DROP COLUMN "redeem_success";
        DROP TABLE IF EXISTS "discordembed";"""


MODELS_STATE = (
    "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"
    "//D3QRHeg="
)
