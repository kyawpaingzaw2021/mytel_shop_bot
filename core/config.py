from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    SUPER_ADMIN_ID: int
    SUPER_ADMIN_ID_2: int = 0
    DATABASE_URL: str
    DB_NAME: str = "mytel_shop"
    DB_USER: str = "mytel"
    DB_PASSWORD: str = ""
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 5432
    ADMIN_GROUP_ID: int = 0
    NOTIC_CHANNEL_ID: int = 0
    TZ: str = "Asia/Yangon"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


config = Settings()


def is_super_admin(tg_id: int) -> bool:
    if tg_id == config.SUPER_ADMIN_ID:
        return True
    if config.SUPER_ADMIN_ID_2 and tg_id == config.SUPER_ADMIN_ID_2:
        return True
    return False
