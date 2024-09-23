from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "notesnotify" ADD "hours_before" SMALLINT;
        ALTER TABLE "notesnotify" ALTER COLUMN "type" TYPE SMALLINT USING "type"::SMALLINT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "notesnotify" DROP COLUMN "hours_before";
        ALTER TABLE "notesnotify" ALTER COLUMN "type" TYPE SMALLINT USING "type"::SMALLINT;"""
