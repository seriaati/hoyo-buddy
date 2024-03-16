async def upgrade(db) -> str:
    return """
        ALTER TABLE "enkacache" ADD "hoyolab" BYTEA;"""


async def downgrade(db) -> str:
    return """
        ALTER TABLE "enkacache" DROP COLUMN "hoyolab";"""
