"""
11Labs API Client for Text-to-Speech Conversion
Part of the Multi-Modal Chatbot System
"""

import os
import logging
import json
import requests
from typing import Dict, Any, Optional, Tuple, BinaryIO
from dataclasses import dataclass
from enum import Enum
import time
from pathlib import Path
import base64

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VoiceModel(Enum):
    """Available 11Labs voice models."""
    ELEVEN_MONOLINGUAL_V1 = "eleven_monolingual_v1"
    ELEVEN_MULTILINGUAL_V1 = "eleven_multilingual_v1"
    ELEVEN_MULTILINGUAL_V2 = "eleven_multilingual_v2"
    ELEVEN_TURBO_V2 = "eleven_turbo_v2"


class OutputFormat(Enum):
    """Available audio output formats."""
    MP3_22050_32 = "mp3_22050_32"
    MP3_44100_32 = "mp3_44100_32"
    MP3_44100_64 = "mp3_44100_64"
    MP3_44100_96 = "mp3_44100_96"
    MP3_44100_128 = "mp3_44100_128"
    MP3_44100_192 = "mp3_44100_192"
    PCM_16000 = "pcm_16000"
    PCM_22050 = "pcm_22050"
    PCM_24000 = "pcm_24000"
    PCM_44100 = "pcm_44100"


@dataclass
class VoiceSettings:
    """Voice settings for speech generation."""
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return {
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style": self.style,
            "use_speaker_boost": self.use_speaker_boost
        }


class ElevenLabsClient:
    """Client for interacting with 11Labs Text-to-Speech API."""

    BASE_URL = "https://api.elevenlabs.io/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the 11Labs client.
        
        Args:
            api_key: 11Labs API key. If None, reads from ELEVENLABS_API_KEY environment variable.
        
        Raises:
            ValueError: If API key is not provided.
        """
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key must be provided either as argument or via ELEVENLABS_API_KEY environment variable"
            )
        
        self.session = requests.Session()
        self.session.headers.update({
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        
        logger.info("11Labs client initialized successfully")

    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Make HTTP request to 11Labs API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            **kwargs: Additional arguments for requests
        
        Returns:
            Tuple of (success, response_data)
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            
            if response.status_code == 204:
                return True, None
            
            return True, response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    logger.error(f"Error response: {error_data}")
                except:
                    logger.error(f"Error response text: {e.response.text}")
            return False, None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            return False, None

    def get_voices(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Get list of available voices.
        
        Returns:
            Tuple of (success, voices_data)
        """
        logger.info("Fetching available voices")
        return self._make_request("GET", "voices")

    def get_voice(self, voice_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Get details of a specific voice.
        
        Args:
            voice_id: ID of the voice to retrieve
        
        Returns:
            Tuple of (success, voice_data)
        """
        logger.info(f"Fetching voice details for ID: {voice_id}")
        return self._make_request("GET", f"voices/{voice_id}")

    def text_to_speech(
        self,
        text: str,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # Rachel's voice ID
        model_id: VoiceModel = VoiceModel.ELEVEN_MULTILINGUAL_V2,
        voice_settings: Optional[VoiceSettings] = None,
        output_format: OutputFormat = OutputFormat.MP3_44100_128,
        optimize_streaming_latency: int = 0
    ) -> Tuple[bool, Optional[bytes]]:
        """
        Convert text to speech using 11Labs API.
        
        Args:
            text: Text to convert to speech
            voice_id: ID of the voice to use
            model_id: Voice model to use
            voice_settings: Voice settings for generation
            output_format: Audio output format
            optimize_streaming_latency: Optimization level (0-4)
        
        Returns:
            Tuple of (success, audio_data)
        """
        if not text or not text.strip():
            logger.error("Text cannot be empty")
            return False, None
        
        if len(text) > 5000:
            logger.warning(f"Text length ({len(text)}) exceeds recommended limit")
        
        logger.info(f"Converting text to speech (length: {len(text)} chars)")
        
        # Prepare request data
        data = {
            "text": text,
            "model_id": model_id.value,
            "voice_settings": (voice_settings or VoiceSettings()).to_dict(),
            "output_format": output_format.value
        }
        
        if optimize_streaming_latency:
            data["optimize_streaming_latency"] = optimize_streaming_latency
        
        # Make request with streaming response
        url = f"{self.BASE_URL}/text-to-speech/{voice_id}"
        
        try:
            headers = {
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            }
            
            response = requests.post(
                url,
                json=data,
                headers=headers,
                stream=True,
                timeout=30
            )
            response.raise_for_status()
            
            audio_data = response.content
            logger.info(f"Successfully generated audio ({len(audio_data)} bytes)")
            return True, audio_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Text-to-speech request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    logger.error(f"Error details: {error_data}")
                except:
                    logger.error(f"Error response: {e.response.text}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error in text-to-speech: {str(e)}")
            return False, None

    def text_to_speech_stream(
        self,
        text: str,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",
        model_id: VoiceModel = VoiceModel.ELEVEN_MULTILINGUAL_V2,
        voice_settings: Optional[VoiceSettings] = None,
        output_format: OutputFormat = OutputFormat.MP3_44100_128
    ) -> Optional[requests.Response]:
        """
        Convert text to speech with streaming response.
        
        Args:
            text: Text to convert to speech
            voice_id: ID of the voice to use
            model_id: Voice model to use
            voice_settings: Voice settings for generation
            output_format: Audio output format
        
        Returns:
            Streaming response object or None if failed
        """
        if not text or not text.strip():
            logger.error("Text cannot be empty")
            return None
        
        logger.info(f"Streaming text-to-speech (length: {len(text)} chars)")
        
        data = {
            "text": text,
            "model_id": model_id.value,
            "voice_settings": (voice_settings or VoiceSettings()).to_dict(),
            "output_format": output_format.value
        }
        
        url = f"{self.BASE_URL}/text-to-speech/{voice_id}/stream"
        
        try:
            headers = {
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            }
            
            response = requests.post(
                url,
                json=data,
                headers=headers,
                stream=True,
                timeout=30
            )
            response.raise_for_status()
            
            logger.info("Streaming audio response initiated")
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Streaming request failed: {str(e)}")
            return None

    def save_audio_to_file(
        self,
        audio_data: bytes,
        filepath: str,
        format: str = "mp3"
    ) -> bool:
        """
        Save audio data to file.
        
        Args:
            audio_data: Binary audio data
            filepath: Path to save the file
            format: Audio format (mp3, wav, etc.)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'wb') as f:
                f.write(audio_data)
            
            logger.info(f"Audio saved to {filepath} ({len(audio_data)} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save audio to file: {str(e)}")
            return False

    def text_to_speech_and_save(
        self,
        text: str,
        output_file: str,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",
        **kwargs
    ) -> Tuple[bool, Optional[str]]:
        """
        Convert text to speech and save to file in one operation.
        
        Args:
            text: Text to convert
            output_file: Path to save the