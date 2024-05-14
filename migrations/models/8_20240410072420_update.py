from __future__ import annotations


async def upgrade(db) -> str:
    return """
        ALTER TABLE "hoyoaccount" ADD "redeemed_codes" JSONB NOT NULL DEFAULT '[]';
        ALTER TABLE "hoyoaccount" ADD "auto_redeem" BOOL NOT NULL  DEFAULT True;"""


async def downgrade(db) -> str:
    return """
        ALTER TABLE "hoyoaccount" DROP COLUMN "redeemed_codes";
        ALTER TABLE "hoyoaccount" DROP COLUMN "auto_redeem";"""
