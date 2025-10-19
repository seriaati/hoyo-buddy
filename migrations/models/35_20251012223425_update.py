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


MODELS_STATE = (
    "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"
    "WnIk+IdYVBfWAxx7+vF/Nmjy9g=="
)