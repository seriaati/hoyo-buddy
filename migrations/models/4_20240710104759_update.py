from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "challengehistory" ALTER COLUMN "challenge_type" TYPE VARCHAR(32) USING "challenge_type"::VARCHAR(32);
        ALTER TABLE "notesnotify" ALTER COLUMN "type" TYPE SMALLINT USING "type"::SMALLINT;
        ALTER TABLE "settings" ADD "gi_card_temp" VARCHAR(32) NOT NULL  DEFAULT 'hb1';
        ALTER TABLE "settings" ADD "hsr_card_temp" VARCHAR(32) NOT NULL  DEFAULT 'hb1';
        ALTER TABLE "settings" ADD "zzz_card_temp" VARCHAR(32) NOT NULL  DEFAULT 'hb1';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "settings" DROP COLUMN "gi_card_temp";
        ALTER TABLE "settings" DROP COLUMN "hsr_card_temp";
        ALTER TABLE "settings" DROP COLUMN "zzz_card_temp";
        ALTER TABLE "notesnotify" ALTER COLUMN "type" TYPE SMALLINT USING "type"::SMALLINT;
        ALTER TABLE "challengehistory" ALTER COLUMN "challenge_type" TYPE VARCHAR(32) USING "challenge_type"::VARCHAR(32);"""
