import os
import sys
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

def get_default_data_dir() -> Path:
    """Return OS-appropriate directory for MailGraph local data."""
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        base = Path(app_data) if app_data else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg_data = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg_data) if xdg_data else Path.home() / ".local" / "share"
        
    data_dir = base / "Mailgraph"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAILGRAPH_")
    
    app_name: str = "MailGraph"
    app_version: str = "0.1.0"
    data_dir: Path = get_default_data_dir()
    db_path: str = str(get_default_data_dir() / "mailgraph.db")
    host: str = "127.0.0.1"
    port: int = 28491
    
    # Privacy & Local-first settings
    telemetry: bool = False
    index_message_bodies: bool = False
    download_attachments_automatically: bool = False
    
    # Local AI (optional, local-only Ollama)
    local_ai_enabled: bool = False
    local_ai_endpoint: str = "http://127.0.0.1:11434"
    local_ai_model: str = "llama3.2"
    
    # Action safety
    default_delete_mode: str = "trash"
    require_preview: bool = True
    require_confirmation: bool = True
    backup_before_mutation: bool = True

settings = Settings()
