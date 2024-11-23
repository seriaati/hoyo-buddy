from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "cardsettings" ADD "highlight_special_stats" BOOL NOT NULL  DEFAULT True;
        ALTER TABLE "notesnotify" ALTER COLUMN "type" TYPE SMALLINT USING "type"::SMALLINT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "notesnotify" ALTER COLUMN "type" TYPE SMALLINT USING "type"::SMALLINT;
        ALTER TABLE "cardsettings" DROP COLUMN "highlight_special_stats";"""
