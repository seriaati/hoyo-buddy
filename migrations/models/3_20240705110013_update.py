from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" ALTER COLUMN "game" TYPE VARCHAR(32) USING "game"::VARCHAR(32);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" ALTER COLUMN "game" TYPE VARCHAR(32) USING "game"::VARCHAR(32);"""


MODELS_STATE = (
    "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"
    "6apETMYwx3F/PXWDlG+/XyPwCgPNI="
)
