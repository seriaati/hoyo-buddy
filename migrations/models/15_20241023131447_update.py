from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "cardsettings" ADD "show_substat_rolls" BOOL NOT NULL  DEFAULT True;
        ALTER TABLE "settings" ADD "team_card_substat_rolls" BOOL NOT NULL  DEFAULT True;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "settings" DROP COLUMN "team_card_substat_rolls";
        ALTER TABLE "cardsettings" DROP COLUMN "show_substat_rolls";"""
