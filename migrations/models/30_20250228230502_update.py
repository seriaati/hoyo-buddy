from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" ADD "last_redeem_time" TIMESTAMPTZ;
        ALTER TABLE "hoyoaccount" ADD "last_checkin_time" TIMESTAMPTZ;
        ALTER TABLE "hoyoaccount" ADD "last_mimo_buy_time" TIMESTAMPTZ;
        ALTER TABLE "hoyoaccount" ADD "last_mimo_draw_time" TIMESTAMPTZ;
        ALTER TABLE "hoyoaccount" ADD "last_mimo_task_time" TIMESTAMPTZ;
        DROP TABLE IF EXISTS "commandmetric";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" DROP COLUMN "last_redeem_time";
        ALTER TABLE "hoyoaccount" DROP COLUMN "last_checkin_time";
        ALTER TABLE "hoyoaccount" DROP COLUMN "last_mimo_buy_time";
        ALTER TABLE "hoyoaccount" DROP COLUMN "last_mimo_draw_time";
        ALTER TABLE "hoyoaccount" DROP COLUMN "last_mimo_task_time";"""
