from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "settings" ADD "enable_dyk" BOOL NOT NULL  DEFAULT True;
        ALTER TABLE "settings" ALTER COLUMN "zzz_card_temp" SET DEFAULT 'hb2';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "settings" DROP COLUMN "enable_dyk";
        ALTER TABLE "settings" ALTER COLUMN "zzz_card_temp" SET DEFAULT 'hb1';"""


MODELS_STATE = (
    "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"
)
