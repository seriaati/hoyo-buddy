from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "gachastats" ADD "avg_3star_pulls" DOUBLE PRECISION NOT NULL DEFAULT 0;
        ALTER TABLE "hoyoaccount" DROP COLUMN "mimo_minimum_point";
        ALTER TABLE "settings" DROP COLUMN "zzz_dark_mode";
        ALTER TABLE "settings" DROP COLUMN "gi_dark_mode";
        ALTER TABLE "settings" DROP COLUMN "hsr_dark_mode";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "settings" ADD "zzz_dark_mode" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "settings" ADD "gi_dark_mode" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "settings" ADD "hsr_dark_mode" BOOL NOT NULL DEFAULT False;
        ALTER TABLE "gachastats" DROP COLUMN "avg_3star_pulls";
        ALTER TABLE "hoyoaccount" ADD "mimo_minimum_point" INT NOT NULL DEFAULT 0;"""


MODELS_STATE = (
    "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"
    "Y1fWq6nh4iYYlQSlDRyw8O+Pl/jAr4IA=="
)
