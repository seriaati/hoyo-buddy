from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "settings" ADD "team_card_dark_mode" BOOL NOT NULL  DEFAULT False;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "settings" DROP COLUMN "team_card_dark_mode";"""


MODELS_STATE = (
    "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"
    "H6r1//B/v3l5s="
)
