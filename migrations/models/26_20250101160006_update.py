from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "accountnotifsettings" ADD "web_events" BOOL NOT NULL  DEFAULT False;
        COMMENT ON COLUMN "notesnotify"."type" IS 'RESIN: 1
REALM_CURRENCY: 2
TB_POWER: 3
GI_EXPED: 4
HSR_EXPED: 5
PT: 6
GI_DAILY: 7
HSR_DAILY: 8
RESIN_DISCOUNT: 9
ECHO_OF_WAR: 10
RESERVED_TB_POWER: 11
BATTERY: 12
ZZZ_DAILY: 13
SCRATCH_CARD: 14
VIDEO_STORE: 15
PLANAR_FISSURE: 16
STAMINA: 17
ZZZ_BOUNTY: 18
RIDU_POINTS: 19';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        COMMENT ON COLUMN "notesnotify"."type" IS 'RESIN: 1
REALM_CURRENCY: 2
TB_POWER: 3
GI_EXPED: 4
HSR_EXPED: 5
PT: 6
GI_DAILY: 7
HSR_DAILY: 8
RESIN_DISCOUNT: 9
ECHO_OF_WAR: 10
RESERVED_TB_POWER: 11
BATTERY: 12
ZZZ_DAILY: 13
SCRATCH_CARD: 14
VIDEO_STORE: 15
PLANAR_FISSURE: 16
STAMINA: 17';
        ALTER TABLE "accountnotifsettings" DROP COLUMN "web_events";"""
