from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "cardsettings" ADD "show_rank" BOOL NOT NULL  DEFAULT True;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "cardsettings" DROP COLUMN "show_rank";"""


MODELS_STATE = (
    "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"
)
