from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


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


MODELS_STATE = (
    "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"
)
