from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


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


MODELS_STATE = (
    "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"
    "XQrcVQ/JYcifwRFuWF9QDHm378H2Htgfs="
)
