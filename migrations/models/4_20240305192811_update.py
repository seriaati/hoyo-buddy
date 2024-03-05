async def upgrade(db) -> str:
    return """
        ALTER TABLE "hoyoaccount" ADD "current" BOOL NOT NULL  DEFAULT False;"""


async def downgrade(db) -> str:
    return """
        ALTER TABLE "hoyoaccount" DROP COLUMN "current";"""
