from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "challengehistory" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "uid" BIGINT NOT NULL,
    "season_id" INT NOT NULL,
    "name" VARCHAR(64),
    "challenge_type" VARCHAR(32) NOT NULL,
    "data" BYTEA,
    "start_time" TIMESTAMPTZ NOT NULL,
    "end_time" TIMESTAMPTZ NOT NULL,
    "lang" VARCHAR(5),
    "json_data" JSONB,
    CONSTRAINT "uid_challengehi_uid_c138dc" UNIQUE ("uid", "season_id", "challenge_type")
);
CREATE INDEX IF NOT EXISTS "idx_challengehi_uid_29a8a4" ON "challengehistory" ("uid");
COMMENT ON COLUMN "challengehistory"."challenge_type" IS 'SPIRAL_ABYSS: Spiral abyss\nMOC: Memory of chaos\nPURE_FICTION: Pure fiction\nAPC_SHADOW: Apocalyptic shadow\nIMG_THEATER: img_theater_large_block_title\nSHIYU_DEFENSE: Shiyu defense\nASSAULT: zzz_deadly_assault\nHARD_CHALLENGE: hard_challenge\nANOMALY: anomaly_arbitration';
CREATE TABLE IF NOT EXISTS "dmchannel" (
    "id" BIGINT NOT NULL PRIMARY KEY,
    "user_id" BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS "gachastats" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "account_id" INT NOT NULL,
    "lifetime_pulls" INT NOT NULL,
    "avg_5star_pulls" DOUBLE PRECISION NOT NULL,
    "avg_4star_pulls" DOUBLE PRECISION NOT NULL,
    "avg_3star_pulls" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "win_rate" DOUBLE PRECISION NOT NULL,
    "game" VARCHAR(32) NOT NULL,
    "banner_type" INT NOT NULL,
    CONSTRAINT "uid_gachastats_account_7c0c6d" UNIQUE ("account_id", "banner_type", "game")
);
COMMENT ON COLUMN "gachastats"."game" IS 'GENSHIN: Genshin Impact\nSTARRAIL: Honkai: Star Rail\nHONKAI: Honkai Impact 3rd\nZZZ: Zenless Zone Zero\nTOT: Tears of Themis';
CREATE TABLE IF NOT EXISTS "jsonfile" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "data" JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS "idx_jsonfile_name_1de105" ON "jsonfile" ("name");
CREATE TABLE IF NOT EXISTS "leaderboard" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "type" VARCHAR(32) NOT NULL,
    "game" VARCHAR(32) NOT NULL,
    "value" DOUBLE PRECISION NOT NULL,
    "uid" BIGINT NOT NULL,
    "rank" INT NOT NULL,
    "username" VARCHAR(32) NOT NULL,
    "extra_info" JSONB,
    CONSTRAINT "uid_leaderboard_type_58f2b6" UNIQUE ("type", "game", "uid")
);
COMMENT ON COLUMN "leaderboard"."type" IS 'ACHIEVEMENT: achievement_lb_title\nCHEST: chest_lb_title\nMAX_FRIENDSHIP: max_friendship_lb_title\nABYSS_DMG: abyss_dmg_lb_title\nTHEATER_DMG: theater_dmg_lb_title';
COMMENT ON COLUMN "leaderboard"."game" IS 'GENSHIN: Genshin Impact\nSTARRAIL: Honkai: Star Rail\nHONKAI: Honkai Impact 3rd\nZZZ: Zenless Zone Zero\nTOT: Tears of Themis';
CREATE TABLE IF NOT EXISTS "user" (
    "id" BIGINT NOT NULL PRIMARY KEY,
    "temp_data" JSONB NOT NULL,
    "last_interaction" TIMESTAMPTZ,
    "dismissibles" JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS "cardsettings" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "character_id" VARCHAR(8) NOT NULL,
    "dark_mode" BOOL NOT NULL,
    "custom_images" JSONB NOT NULL,
    "custom_primary_color" VARCHAR(7),
    "current_image" TEXT,
    "current_team_image" TEXT,
    "template" VARCHAR(32) NOT NULL DEFAULT 'hb1',
    "show_rank" BOOL NOT NULL DEFAULT True,
    "show_substat_rolls" BOOL NOT NULL DEFAULT True,
    "highlight_special_stats" BOOL NOT NULL DEFAULT True,
    "highlight_substats" JSONB NOT NULL,
    "use_m3_art" BOOL NOT NULL DEFAULT False,
    "game" VARCHAR(32),
    "user_id" BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_cardsetting_charact_58a731" UNIQUE ("character_id", "user_id", "game")
);
COMMENT ON COLUMN "cardsettings"."game" IS 'GENSHIN: Genshin Impact\nSTARRAIL: Honkai: Star Rail\nHONKAI: Honkai Impact 3rd\nZZZ: Zenless Zone Zero\nTOT: Tears of Themis';
CREATE TABLE IF NOT EXISTS "customimage" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" VARCHAR(100),
    "url" TEXT,
    "character_id" VARCHAR(8) NOT NULL,
    "user_id" BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_customimage_charact_e2ae7a" UNIQUE ("character_id", "user_id", "url")
);
CREATE TABLE IF NOT EXISTS "hoyoaccount" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "uid" BIGINT NOT NULL,
    "username" VARCHAR(32) NOT NULL,
    "game" VARCHAR(32) NOT NULL,
    "cookies" TEXT NOT NULL,
    "server" VARCHAR(32) NOT NULL,
    "device_id" VARCHAR(36),
    "device_fp" VARCHAR(13),
    "region" VARCHAR(2) NOT NULL,
    "nickname" VARCHAR(32),
    "public" BOOL NOT NULL DEFAULT True,
    "mimo_minimum_point" INT NOT NULL DEFAULT 0,
    "daily_checkin" BOOL NOT NULL DEFAULT True,
    "auto_redeem" BOOL NOT NULL DEFAULT True,
    "mimo_auto_task" BOOL NOT NULL DEFAULT True,
    "mimo_auto_buy" BOOL NOT NULL DEFAULT False,
    "mimo_auto_draw" BOOL NOT NULL DEFAULT False,
    "last_checkin_time" TIMESTAMPTZ,
    "last_mimo_task_time" TIMESTAMPTZ,
    "last_mimo_buy_time" TIMESTAMPTZ,
    "last_mimo_draw_time" TIMESTAMPTZ,
    "last_redeem_time" TIMESTAMPTZ,
    "current" BOOL NOT NULL DEFAULT False,
    "redeemed_codes" JSONB NOT NULL,
    "mimo_all_claimed_time" TIMESTAMPTZ,
    "user_id" BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_hoyoaccount_uid_caad37" UNIQUE ("uid", "game", "user_id")
);
CREATE INDEX IF NOT EXISTS "idx_hoyoaccount_uid_e838aa" ON "hoyoaccount" ("uid");
COMMENT ON COLUMN "hoyoaccount"."game" IS 'GENSHIN: Genshin Impact\nSTARRAIL: Honkai: Star Rail\nHONKAI: Honkai Impact 3rd\nZZZ: Zenless Zone Zero\nTOT: Tears of Themis';
COMMENT ON COLUMN "hoyoaccount"."region" IS 'OVERSEAS: os\nCHINESE: cn';
CREATE TABLE IF NOT EXISTS "accountnotifsettings" (
    "notify_on_checkin_failure" BOOL NOT NULL DEFAULT True,
    "notify_on_checkin_success" BOOL NOT NULL DEFAULT True,
    "mimo_task_success" BOOL NOT NULL DEFAULT True,
    "mimo_task_failure" BOOL NOT NULL DEFAULT True,
    "mimo_buy_success" BOOL NOT NULL DEFAULT True,
    "mimo_buy_failure" BOOL NOT NULL DEFAULT True,
    "mimo_draw_success" BOOL NOT NULL DEFAULT True,
    "mimo_draw_failure" BOOL NOT NULL DEFAULT True,
    "redeem_success" BOOL NOT NULL DEFAULT True,
    "redeem_failure" BOOL NOT NULL DEFAULT True,
    "web_events" BOOL NOT NULL DEFAULT False,
    "account_id" INT NOT NULL PRIMARY KEY REFERENCES "hoyoaccount" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "discordembed" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "data" JSONB NOT NULL,
    "task_type" VARCHAR(20) NOT NULL,
    "type" VARCHAR(7) NOT NULL,
    "account_id" INT NOT NULL REFERENCES "hoyoaccount" ("id") ON DELETE CASCADE,
    "user_id" BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "farmnotify" (
    "enabled" BOOL NOT NULL DEFAULT True,
    "item_ids" JSONB NOT NULL,
    "account_id" INT NOT NULL PRIMARY KEY REFERENCES "hoyoaccount" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "gachahistory" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "wish_id" BIGINT NOT NULL,
    "rarity" INT NOT NULL,
    "time" TIMESTAMPTZ NOT NULL,
    "item_id" INT NOT NULL,
    "banner_type" INT NOT NULL,
    "banner_id" INT,
    "num" INT NOT NULL DEFAULT 1,
    "num_since_last" INT NOT NULL DEFAULT 1,
    "game" VARCHAR(32) NOT NULL,
    "account_id" INT NOT NULL REFERENCES "hoyoaccount" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_gachahistor_wish_id_db327c" UNIQUE ("wish_id", "game", "account_id")
);
CREATE INDEX IF NOT EXISTS "idx_gachahistor_account_41d59c" ON "gachahistory" ("account_id");
COMMENT ON COLUMN "gachahistory"."game" IS 'GENSHIN: Genshin Impact\nSTARRAIL: Honkai: Star Rail\nHONKAI: Honkai Impact 3rd\nZZZ: Zenless Zone Zero\nTOT: Tears of Themis';
CREATE TABLE IF NOT EXISTS "notesnotify" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "type" SMALLINT NOT NULL,
    "enabled" BOOL NOT NULL DEFAULT True,
    "last_notif_time" TIMESTAMPTZ,
    "last_check_time" TIMESTAMPTZ,
    "est_time" TIMESTAMPTZ,
    "notify_interval" SMALLINT NOT NULL,
    "check_interval" SMALLINT NOT NULL,
    "max_notif_count" SMALLINT NOT NULL DEFAULT 5,
    "current_notif_count" SMALLINT NOT NULL DEFAULT 0,
    "threshold" SMALLINT,
    "notify_time" SMALLINT,
    "notify_weekday" SMALLINT,
    "hours_before" SMALLINT,
    "account_id" INT NOT NULL REFERENCES "hoyoaccount" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_notesnotify_type_0526b8" UNIQUE ("type", "account_id")
);
COMMENT ON COLUMN "notesnotify"."type" IS 'RESIN: 1\nREALM_CURRENCY: 2\nTB_POWER: 3\nGI_EXPED: 4\nHSR_EXPED: 5\nPT: 6\nGI_DAILY: 7\nHSR_DAILY: 8\nRESIN_DISCOUNT: 9\nECHO_OF_WAR: 10\nRESERVED_TB_POWER: 11\nBATTERY: 12\nZZZ_DAILY: 13\nSCRATCH_CARD: 14\nVIDEO_STORE: 15\nPLANAR_FISSURE: 16\nSTAMINA: 17\nZZZ_BOUNTY: 18\nRIDU_POINTS: 19';
CREATE TABLE IF NOT EXISTS "settings" (
    "lang" VARCHAR(10),
    "dark_mode" BOOL NOT NULL DEFAULT True,
    "gi_card_temp" VARCHAR(32) NOT NULL DEFAULT 'hb1',
    "hsr_card_temp" VARCHAR(32) NOT NULL DEFAULT 'hb1',
    "zzz_card_temp" VARCHAR(32) NOT NULL DEFAULT 'hb2',
    "team_card_dark_mode" BOOL NOT NULL DEFAULT False,
    "enable_dyk" BOOL NOT NULL DEFAULT True,
    "gi_dark_mode" BOOL NOT NULL DEFAULT False,
    "hsr_dark_mode" BOOL NOT NULL DEFAULT False,
    "zzz_dark_mode" BOOL NOT NULL DEFAULT False,
    "user_id" BIGINT NOT NULL PRIMARY KEY REFERENCES "user" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
)
