from __future__ import annotations
from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "jsonfile" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "data" JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_jsonfile_name_1de105" ON "jsonfile" ("name");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "jsonfile";"""
