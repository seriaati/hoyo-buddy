async def upgrade(db) -> str:
    return """
        ALTER TABLE "cardsettings" ADD "template" VARCHAR(32) NOT NULL  DEFAULT 'hb1';"""


async def downgrade(db) -> str:
    return """
        ALTER TABLE "cardsettings" DROP COLUMN "template";"""
