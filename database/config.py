from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    
    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_port: str = Field(default="5432", validation_alias="DB_PORT")
    db_name: str = Field(default="appdb", validation_alias="DB_NAME")
    db_user: str = Field(default="appuser", validation_alias="DB_USER")
    db_pass: str = Field(default="password", validation_alias="DB_PASS")


settings = Settings()
