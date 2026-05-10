from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Gemini
    gemini_api_key: str = ""

    # Google Sheets / Gmail
    google_sheets_id: str = ""
    google_credentials_path: str = "./credentials.json"
    google_token_path: str = "./token.json"

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # Cron auth
    cron_secret: str = "dev-secret"

    # Behavior
    send_emails_for_real: bool = False
    seed_on_startup: bool = True  # set False in production with a real Sheet
    user_email: str = "you@example.com"
    app_base_url: str = "http://localhost:3000"

    # CORS
    allowed_origins: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
