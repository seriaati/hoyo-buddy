async def upgrade(db) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "enkacache" (
    "uid" SERIAL NOT NULL PRIMARY KEY,
    "hsr" JSONB NOT NULL,
    "genshin" JSONB NOT NULL
);"""


async def downgrade(db) -> str:
    return """
        DROP TABLE IF EXISTS "enkacache";"""
