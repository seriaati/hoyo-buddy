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
HARD_CHALLENGE: hard_challenge
ANOMALY: anomaly_arbitration';
        ALTER TABLE "gachahistory" ALTER COLUMN "num" SET DEFAULT 1;
        ALTER TABLE "gachahistory" ALTER COLUMN "num_since_last" SET DEFAULT 1;
        ALTER TABLE "hoyoaccount" ADD "mimo_minimum_point" INT NOT NULL DEFAULT 0;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "hoyoaccount" DROP COLUMN "mimo_minimum_point";
        ALTER TABLE "gachahistory" ALTER COLUMN "num" DROP DEFAULT;
        ALTER TABLE "gachahistory" ALTER COLUMN "num_since_last" DROP DEFAULT;
        COMMENT ON COLUMN "challengehistory"."challenge_type" IS 'SPIRAL_ABYSS: Spiral abyss
MOC: Memory of chaos
PURE_FICTION: Pure fiction
APC_SHADOW: Apocalyptic shadow
IMG_THEATER: img_theater_large_block_title
SHIYU_DEFENSE: Shiyu defense
ASSAULT: zzz_deadly_assault
HARD_CHALLENGE: hard_challenge';"""
