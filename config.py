"""
Configuration Management Module for Chatbot Application
Handles API keys, settings, and environment variables securely
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pathlib import Path
from dotenv import load_dotenv
import secrets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class APIConfig:
    """Data class for API configuration"""
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    pixabay_api_key: str = ""
    survey_api_key: str = ""
    survey_api_url: str = "https://api.surveymonkey.com/v3"


@dataclass
class AppConfig:
    """Data class for application configuration"""
    app_name: str = "Multi-Language AI Chatbot"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 5000
    secret_key: str = ""
    upload_folder: str = "uploads"
    max_upload_size: int = 16 * 1024 * 1024  # 16MB
    supported_languages: List[str] = None
    
    def __post_init__(self):
        """Initialize default values"""
        if self.supported_languages is None:
            self.supported_languages = ["en", "ur", "hi", "roman_english"]
        if not self.secret_key:
            self.secret_key = secrets.token_hex(32)


class ConfigManager:
    """
    Manages application configuration and environment variables
    Implements singleton pattern for consistent configuration access
    """
    
    _instance = None
    _config_loaded = False
    
    def __new__(cls):
        """Singleton pattern implementation"""
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize configuration manager"""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.api_config = APIConfig()
            self.app_config = AppConfig()
            self._config_file = Path(".config.json")
            self._env_file = Path(".env")
            self._load_configuration()
    
    def _load_configuration(self) -> None:
        """
        Load configuration from environment variables and config file
        Priority: Environment variables > Config file > Defaults
        """
        try:
            # Load environment variables from .env file if exists
            if self._env_file.exists():
                load_dotenv(self._env_file)
                logger.info("Loaded environment variables from .env file")
            
            # Load from config file if exists
            if self._config_file.exists():
                self._load_from_file()
            
            # Override with environment variables
            self._load_from_env()
            
            # Validate configuration
            self._validate_config()
            
            self._config_loaded = True
            logger.info("Configuration loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            raise
    
    def _load_from_file(self) -> None:
        """Load configuration from JSON file"""
        try:
            with open(self._config_file, 'r') as f:
                config_data = json.load(f)
            
            # Load API config
            api_data = config_data.get('api_config', {})
            for key, value in api_data.items():
                if hasattr(self.api_config, key):
                    setattr(self.api_config, key, value)
            
            # Load App config
            app_data = config_data.get('app_config', {})
            for key, value in app_data.items():
                if hasattr(self.app_config, key):
                    setattr(self.app_config, key, value)
            
            logger.info(f"Configuration loaded from {self._config_file}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {str(e)}")
        except Exception as e:
            logger.error(f"Error reading config file: {str(e)}")
    
    def _load_from_env(self) -> None:
        """Load configuration from environment variables"""
        try:
            # API Configuration
            self.api_config.deepseek_api_key = os.getenv(
                'DEEPSEEK_API_KEY', 
                self.api_config.deepseek_api_key
            )
            self.api_config.deepseek_model = os.getenv(
                'DEEPSEEK_MODEL', 
                self.api_config.deepseek_model
            )
            self.api_config.deepseek_base_url = os.getenv(
                'DEEPSEEK_BASE_URL', 
                self.api_config.deepseek_base_url
            )
            self.api_config.elevenlabs_api_key = os.getenv(
                'ELEVENLABS_API_KEY', 
                self.api_config.elevenlabs_api_key
            )
            self.api_config.elevenlabs_voice_id = os.getenv(
                'ELEVENLABS_VOICE_ID', 
                self.api_config.elevenlabs_voice_id
            )
            self.api_config.pixabay_api_key = os.getenv(
                'PIXABAY_API_KEY', 
                self.api_config.pixabay_api_key
            )
            self.api_config.survey_api_key = os.getenv(
                'SURVEY_API_KEY', 
                self.api_config.survey_api_key
            )
            self.api_config.survey_api_url = os.getenv(
                'SURVEY_API_URL', 
                self.api_config.survey_api_url
            )
            
            # App Configuration
            self.app_config.app_name = os.getenv(
                'APP_NAME', 
                self.app_config.app_name
            )
            self.app_config.debug = os.getenv(
                'DEBUG', 
                str(self.app_config.debug)
            ).lower() == 'true'
            self.app_config.host = os.getenv(
                'HOST', 
                self.app_config.host
            )
            self.app_config.port = int(os.getenv(
                'PORT', 
                str(self.app_config.port)
            ))
            self.app_config.secret_key = os.getenv(
                'SECRET_KEY', 
                self.app_config.secret_key
            )
            self.app_config.upload_folder = os.getenv(
                'UPLOAD_FOLDER', 
                self.app_config.upload_folder
            )
            
            # Parse supported languages
            langs_env = os.getenv('SUPPORTED_LANGUAGES')
            if langs_env:
                self.app_config.supported_languages = [
                    lang.strip() for lang in langs_env.split(',')
                ]
            
            logger.info("Configuration loaded from environment variables")
            
        except ValueError as e:
            logger.error(f"Error parsing environment variable: {str(e)}")
        except Exception as e:
            logger.error(f"Error loading from environment: {str(e)}")
    
    def _validate_config(self) -> None:
        """Validate configuration values"""
        try:
            # Validate required API keys
            required_keys = [
                ('DEEPSEEK_API_KEY', self.api_config.deepseek_api_key),
                ('ELEVENLABS_API_KEY', self.api_config.elevenlabs_api_key),
                ('PIXABAY_API_KEY', self.api_config.pixabay_api_key),
            ]
            
            missing_keys = []
            for key_name, key_value in required_keys:
                if not key_value or key_value.strip() == "":
                    missing_keys.append(key_name)
            
            if missing_keys:
                logger.warning(f"Missing API keys: {', '.join(missing_keys)}")
            
            # Validate port range
            if not (1 <= self.app_config.port <= 65535):
                raise ValueError(f"Invalid port number: {self.app_config.port}")
            
            # Ensure upload folder exists
            upload_path = Path(self.app_config.upload_folder)
            upload_path.mkdir(exist_ok=True)
            
            logger.info("Configuration validation completed")
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {str(e)}")
            raise
    
    def save_config(self) -> bool:
        """
        Save current configuration to file
        
        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            config_data = {
                'api_config': asdict(self.api_config),
                'app_config': asdict(self.app_config)
            }
            
            with open(self._config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Configuration saved to {self._config_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            return False
    
    def update_api_key(self, service: str, api_key: str) -> bool:
        """
        Update API key for a specific service
        
        Args:
            service: Service name (deepseek, elevenlabs, pixabay, survey)
            api_key: New API key
            
        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            service = service.lower()
            
            if service == 'deepseek':
                self.api_config.deepseek_api_key = api_key
            elif service == 'elevenlabs':
                self.api_config.elevenlabs_api_key = api_key
            elif service == 'pixabay':
                self.api_config.pixabay_api_key = api_key
            elif service == 'survey':
                self.api_config.survey_api_key = api_key
            else:
                logger.error(f"Unknown service: {service}")
                return False
            
            logger.info(f"API key updated for service: {service}")
            return self.save_config()
            
        except Exception as e:
            logger.error(f"Error updating API key: {str(e)}")
            return False
    
    def get_config_summary(self) -> Dict[str, Any]:
        """
        Get a safe summary of configuration (without sensitive data)
        
        Returns:
            Dict containing configuration summary
        """
        api_config_safe = asdict(self.api_config)
        # Mask API keys for security
        for key in api_config_safe:
            if 'key' in key.lower() and api_config_safe[key]:
                api_config_safe[key] = f"{api_config_safe[key][:8]}...{api_config_safe[key][-4:]}"
        
        return {
            'api_config': api_config_safe,
            'app_config': asdict(self.app_config),
            'config_loaded': self._config_loaded
        }
    
    def is_configured(self) -> bool:
        """
        Check if essential configuration is loaded
        
        Returns:
            bool: True if essential config is loaded
        """
        return (
            self._config_loaded and
            bool(self.api_config.deepseek_api_key) and
            bool(self.api_config.elevenlabs_api_key) and
            bool(self.api_config.pixabay_api_key)
        )
    
    def get_flask_config(self) -> Dict[str, Any]:
        """