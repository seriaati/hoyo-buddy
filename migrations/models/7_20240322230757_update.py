async def upgrade(db) -> str:
    return """
        ALTER TABLE "user" ADD "last_interaction" TIMESTAMPTZ;"""


async def downgrade(db) -> str:
    return """
        ALTER TABLE "user" DROP COLUMN "last_interaction";"""
