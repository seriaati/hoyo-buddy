from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" ADD "accompany_characters" JSONB NOT NULL DEFAULT '[]';
        UPDATE "hoyoaccount" SET "accompany_characters" = jsonb_build_array(
            jsonb_build_object('role_id', "accompany_role_id", 'topic_id', "accompany_topic_id")
        ) WHERE "accompany_role_id" IS NOT NULL AND "accompany_topic_id" IS NOT NULL;
        ALTER TABLE "hoyoaccount" DROP COLUMN "accompany_topic_id";
        ALTER TABLE "hoyoaccount" DROP COLUMN "accompany_role_id";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" ADD "accompany_topic_id" INT;
        ALTER TABLE "hoyoaccount" ADD "accompany_role_id" INT;
        UPDATE "hoyoaccount" SET
            "accompany_role_id" = ("accompany_characters"->0->>'role_id')::INT,
            "accompany_topic_id" = ("accompany_characters"->0->>'topic_id')::INT;
        ALTER TABLE "hoyoaccount" DROP COLUMN "accompany_characters";"""


MODELS_STATE = (
    "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"
)
