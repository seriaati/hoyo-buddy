from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "cardsettings" ADD "game" VARCHAR(32);
        DROP TABLE IF EXISTS "taskleftover";
        """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "cardsettings" DROP COLUMN "game";
        """
