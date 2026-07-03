from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "accountnotifsettings" ADD "notify_on_accompany_failure" BOOL NOT NULL DEFAULT True;
        ALTER TABLE "accountnotifsettings" ADD "notify_on_accompany_success" BOOL NOT NULL DEFAULT True;
        ALTER TABLE "hoyoaccount" ADD "accompany_role_id" INT;
        ALTER TABLE "hoyoaccount" ADD "accompany_topic_id" INT;
        ALTER TABLE "hoyoaccount" ADD "accompany_checkin" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "hoyoaccount" ADD "last_accompany_time" TIMESTAMPTZ;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" DROP COLUMN "accompany_role_id";
        ALTER TABLE "hoyoaccount" DROP COLUMN "accompany_topic_id";
        ALTER TABLE "hoyoaccount" DROP COLUMN "accompany_checkin";
        ALTER TABLE "hoyoaccount" DROP COLUMN "last_accompany_time";
        ALTER TABLE "accountnotifsettings" DROP COLUMN "notify_on_accompany_failure";
        ALTER TABLE "accountnotifsettings" DROP COLUMN "notify_on_accompany_success";"""


MODELS_STATE = (
    "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"
)
