from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "enkacache" ADD "hoyolab_zzz" JSONB;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "enkacache" DROP COLUMN "hoyolab_zzz";"""


MODELS_STATE = (
    "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"
)
