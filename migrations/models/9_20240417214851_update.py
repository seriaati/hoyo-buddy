from __future__ import annotations


async def upgrade(db) -> str:
    return """
        ALTER TABLE "hoyoaccount" ADD "public" BOOL NOT NULL  DEFAULT True;"""


async def downgrade(db) -> str:
    return """
        ALTER TABLE "hoyoaccount" DROP COLUMN "public";"""
