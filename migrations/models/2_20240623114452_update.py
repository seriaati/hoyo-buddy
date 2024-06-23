from tortoise import BaseDBAsyncClient


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
COMMENT ON COLUMN "challengehistory"."challenge_type" IS 'SPIRAL_ABYSS: Spiral abyss\nMOC: Memory of chaos\nPURE_FICTION: Pure fiction\nAPC_SHADOW: Apocalyptic shadow';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "challengehistory";"""
