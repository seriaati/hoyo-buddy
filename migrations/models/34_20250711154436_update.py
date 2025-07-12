from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        COMMENT ON COLUMN "challengehistory"."challenge_type" IS 'SPIRAL_ABYSS: Spiral abyss
MOC: Memory of chaos
PURE_FICTION: Pure fiction
APC_SHADOW: Apocalyptic shadow
IMG_THEATER: img_theater_large_block_title
SHIYU_DEFENSE: Shiyu defense
ASSAULT: zzz_deadly_assault
HARD_CHALLENGE: hard_challenge';
        ALTER TABLE "gachahistory" ADD "banner_id" INT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "gachahistory" DROP COLUMN "banner_id";
        COMMENT ON COLUMN "challengehistory"."challenge_type" IS 'SPIRAL_ABYSS: Spiral abyss
MOC: Memory of chaos
PURE_FICTION: Pure fiction
APC_SHADOW: Apocalyptic shadow
IMG_THEATER: img_theater_large_block_title
SHIYU_DEFENSE: Shiyu defense
ASSAULT: zzz_deadly_assault';"""
