from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "challengehistory" ADD "lang" VARCHAR(5);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "challengehistory" DROP COLUMN "lang";"""


MODELS_STATE = (
    "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"
)
