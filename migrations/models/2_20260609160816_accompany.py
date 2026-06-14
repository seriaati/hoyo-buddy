from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "accountnotifsettings" ADD "notify_on_accompany_success" BOOL NOT NULL DEFAULT True;
        ALTER TABLE "accountnotifsettings" ADD "notify_on_accompany_failure" BOOL NOT NULL DEFAULT True;
        ALTER TABLE "hoyoaccount" ADD "accompany_character_name" VARCHAR(64);
        ALTER TABLE "hoyoaccount" ADD "last_accompany_time" TIMESTAMPTZ;
        ALTER TABLE "hoyoaccount" ADD "accompany_checkin" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "hoyoaccount" ADD "accompany_role_id" INT;
        ALTER TABLE "hoyoaccount" ADD "accompany_topic_id" INT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" DROP COLUMN "accompany_character_name";
        ALTER TABLE "hoyoaccount" DROP COLUMN "last_accompany_time";
        ALTER TABLE "hoyoaccount" DROP COLUMN "accompany_checkin";
        ALTER TABLE "hoyoaccount" DROP COLUMN "accompany_role_id";
        ALTER TABLE "hoyoaccount" DROP COLUMN "accompany_topic_id";
        ALTER TABLE "accountnotifsettings" DROP COLUMN "notify_on_accompany_success";
        ALTER TABLE "accountnotifsettings" DROP COLUMN "notify_on_accompany_failure";"""


MODELS_STATE = (
    "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"
    "4fe4gHkg=="
)
