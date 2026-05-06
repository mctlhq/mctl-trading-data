from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    trading_data_token: str = Field(default="", validation_alias="TRADING_DATA_TOKEN")
    cryptopanic_api_key: str = Field(default="", validation_alias="CRYPTOPANIC_API_KEY")
    etherscan_api_key: str = Field(default="", validation_alias="ETHERSCAN_API_KEY")

    watch_symbols: str = Field(default="ETHUSDT", validation_alias="WATCH_SYMBOLS")
    log_level: str = Field(default="info", validation_alias="LOG_LEVEL")

    bybit_ws_url: str = Field(
        default="wss://stream.bybit.com/v5/public/linear",
        validation_alias="BYBIT_WS_URL",
    )
    bitget_ws_url: str = Field(
        default="wss://ws.bitget.com/v2/ws/public",
        validation_alias="BITGET_WS_URL",
    )

    @property
    def symbols(self) -> list[str]:
        return [s.strip().upper() for s in self.watch_symbols.split(",") if s.strip()]


settings = Settings()
