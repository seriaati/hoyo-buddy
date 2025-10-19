from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" ADD "device_fp" VARCHAR(13);
        ALTER TABLE "hoyoaccount" ADD "device_id" VARCHAR(36);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" DROP COLUMN "device_fp";
        ALTER TABLE "hoyoaccount" DROP COLUMN "device_id";"""


MODELS_STATE = (
    "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"
)
