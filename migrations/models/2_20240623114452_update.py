from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "challengehistory" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "uid" BIGINT NOT NULL,
    "season_id" INT NOT NULL,
    "name" VARCHAR(64),
    "challenge_type" VARCHAR(32) NOT NULL,
    "data" BYTEA NOT NULL,
    "start_time" TIMESTAMPTZ NOT NULL,
    "end_time" TIMESTAMPTZ NOT NULL,
    CONSTRAINT "uid_challengehi_uid_c138dc" UNIQUE ("uid", "season_id", "challenge_type")
);
CREATE INDEX IF NOT EXISTS "idx_challengehi_uid_29a8a4" ON "challengehistory" ("uid");
COMMENT ON COLUMN "challengehistory"."challenge_type" IS 'SPIRAL_ABYSS: Spiral abyss
MOC: Memory of chaos
PURE_FICTION: Pure fiction
APC_SHADOW: Apocalyptic shadow';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "challengehistory";"""


MODELS_STATE = (
    "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"
)
