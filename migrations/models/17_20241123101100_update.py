from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "settings" DROP COLUMN "team_card_substat_rolls";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "settings" ADD "team_card_substat_rolls" BOOL NOT NULL  DEFAULT True;"""
