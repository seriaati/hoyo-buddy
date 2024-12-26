from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "accountnotifsettings" ADD "mimo_draw_success" BOOL NOT NULL  DEFAULT True;
        ALTER TABLE "accountnotifsettings" ADD "mimo_draw_failure" BOOL NOT NULL  DEFAULT True;
        COMMENT ON COLUMN "challengehistory"."challenge_type" IS 'SPIRAL_ABYSS: Spiral abyss
MOC: Memory of chaos
PURE_FICTION: Pure fiction
APC_SHADOW: Apocalyptic shadow
IMG_THEATER: img_theater_large_block_title
SHIYU_DEFENSE: Shiyu defense
ASSAULT: zzz_deadly_assault';
        ALTER TABLE "hoyoaccount" ADD "mimo_auto_draw" BOOL NOT NULL  DEFAULT False;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" DROP COLUMN "mimo_auto_draw";
        COMMENT ON COLUMN "challengehistory"."challenge_type" IS 'SPIRAL_ABYSS: Spiral abyss
MOC: Memory of chaos
PURE_FICTION: Pure fiction
APC_SHADOW: Apocalyptic shadow
IMG_THEATER: img_theater_large_block_title
SHIYU_DEFENSE: Shiyu defense';
        ALTER TABLE "accountnotifsettings" DROP COLUMN "mimo_draw_success";
        ALTER TABLE "accountnotifsettings" DROP COLUMN "mimo_draw_failure";"""
