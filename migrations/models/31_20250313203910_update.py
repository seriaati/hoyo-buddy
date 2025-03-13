from tortoise import BaseDBAsyncClient


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
