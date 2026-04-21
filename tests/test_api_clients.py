"""
Unit tests for API client integrations.
Tests cover DeepSeek, ElevenLabs, Pixabay, and Survey API clients.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import os
from typing import Dict, Any

# Import the clients to test
from api.deepseek_client import DeepSeekClient
from api.elevenlabs_client import ElevenLabsClient
from api.pixabay_client import PixabayClient
from api.survey_client import SurveyClient


class TestDeepSeekClient(unittest.TestCase):
    """Test cases for DeepSeek API client."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.api_key = "test_api_key_123"
        self.base_url = "https://api.deepseek.com/v1"
        self.client = DeepSeekClient(api_key=self.api_key, base_url=self.base_url)
        
    def test_initialization(self) -> None:
        """Test client initialization."""
        self.assertEqual(self.client.api_key, self.api_key)
        self.assertEqual(self.client.base_url, self.base_url)
        self.assertEqual(self.client.model, "deepseek-chat")
        self.assertEqual(self.client.max_tokens, 4000)
        
    @patch('api.deepseek_client.requests.post')
    def test_generate_response_success(self, mock_post: Mock) -> None:
        """Test successful response generation."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "This is a test response from DeepSeek."
                }
            }]
        }
        mock_post.return_value = mock_response
        
        # Test data
        prompt = "Hello, how are you?"
        conversation_history = [{"role": "user", "content": "Hi"}]
        
        # Call method
        response = self.client.generate_response(
            prompt=prompt,
            conversation_history=conversation_history
        )
        
        # Assertions
        self.assertEqual(response, "This is a test response from DeepSeek.")
        mock_post.assert_called_once()
        
        # Check request parameters
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], f"{self.base_url}/chat/completions")
        
        headers = call_args[1]['headers']
        self.assertEqual(headers['Authorization'], f"Bearer {self.api_key}")
        self.assertEqual(headers['Content-Type'], 'application/json')
        
    @patch('api.deepseek_client.requests.post')
    def test_generate_response_api_error(self, mock_post: Mock) -> None:
        """Test API error handling."""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_post.return_value = mock_response
        
        # Call method and expect exception
        with self.assertRaises(Exception) as context:
            self.client.generate_response(prompt="Test prompt")
        
        self.assertIn("API request failed", str(context.exception))
        
    @patch('api.deepseek_client.requests.post')
    def test_generate_response_network_error(self, mock_post: Mock) -> None:
        """Test network error handling."""
        # Mock network error
        mock_post.side_effect = Exception("Network error")
        
        # Call method and expect exception
        with self.assertRaises(Exception) as context:
            self.client.generate_response(prompt="Test prompt")
        
        self.assertIn("Network error", str(context.exception))
        
    def test_build_messages(self) -> None:
        """Test message building logic."""
        # Test with history
        prompt = "New question"
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        messages = self.client._build_messages(prompt, history)
        
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "Hello")
        self.assertEqual(messages[-1]["role"], "user")
        self.assertEqual(messages[-1]["content"], "New question")
        
        # Test without history
        messages = self.client._build_messages(prompt, [])
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["content"], prompt)


class TestElevenLabsClient(unittest.TestCase):
    """Test cases for ElevenLabs API client."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.api_key = "test_elevenlabs_key_456"
        self.base_url = "https://api.elevenlabs.io/v1"
        self.client = ElevenLabsClient(api_key=self.api_key, base_url=self.base_url)
        
    def test_initialization(self) -> None:
        """Test client initialization."""
        self.assertEqual(self.client.api_key, self.api_key)
        self.assertEqual(self.client.base_url, self.base_url)
        self.assertEqual(self.client.voice_id, "21m00Tcm4TlvDq8ikWAM")
        self.assertEqual(self.client.model_id, "eleven_monolingual_v1")
        
    @patch('api.elevenlabs_client.requests.post')
    def test_text_to_speech_success(self, mock_post: Mock) -> None:
        """Test successful text-to-speech conversion."""
        # Mock response with audio data
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"fake_audio_data"
        mock_post.return_value = mock_response
        
        # Test data
        text = "Hello, this is a test."
        output_path = "/tmp/test_audio.mp3"
        
        # Call method
        result = self.client.text_to_speech(text=text, output_path=output_path)
        
        # Assertions
        self.assertTrue(result)
        mock_post.assert_called_once()
        
        # Check request parameters
        call_args = mock_post.call_args
        expected_url = f"{self.base_url}/text-to-speech/{self.client.voice_id}"
        self.assertEqual(call_args[0][0], expected_url)
        
        headers = call_args[1]['headers']
        self.assertEqual(headers['xi-api-key'], self.api_key)
        
    @patch('api.elevenlabs_client.requests.post')
    def test_text_to_speech_api_error(self, mock_post: Mock) -> None:
        """Test API error handling."""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"detail": "Invalid API key"}
        mock_post.return_value = mock_response
        
        # Call method and expect exception
        with self.assertRaises(Exception) as context:
            self.client.text_to_speech(text="Test text")
        
        self.assertIn("API request failed", str(context.exception))
        
    @patch('api.elevenlabs_client.requests.post')
    @patch('api.elevenlabs_client.open')
    def test_text_to_speech_file_error(self, mock_open: Mock, mock_post: Mock) -> None:
        """Test file writing error handling."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"fake_audio_data"
        mock_post.return_value = mock_response
        
        # Mock file writing error
        mock_open.side_effect = IOError("Disk full")
        
        # Call method and expect exception
        with self.assertRaises(Exception) as context:
            self.client.text_to_speech(text="Test text")
        
        self.assertIn("Failed to save audio file", str(context.exception))
        
    def test_build_payload(self) -> None:
        """Test payload building."""
        text = "Test text"
        payload = self.client._build_payload(text)
        
        self.assertIn("text", payload)
        self.assertEqual(payload["text"], text)
        self.assertIn("model_id", payload)
        self.assertEqual(payload["model_id"], self.client.model_id)
        self.assertIn("voice_settings", payload)
        self.assertIn("stability", payload["voice_settings"])
        self.assertIn("similarity_boost", payload["voice_settings"])


class TestPixabayClient(unittest.TestCase):
    """Test cases for Pixabay API client."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.api_key = "test_pixabay_key_789"
        self.base_url = "https://pixabay.com/api"
        self.client = PixabayClient(api_key=self.api_key, base_url=self.base_url)
        
    def test_initialization(self) -> None:
        """Test client initialization."""
        self.assertEqual(self.client.api_key, self.api_key)
        self.assertEqual(self.client.base_url, self.base_url)
        self.assertEqual(self.client.per_page, 20)
        
    @patch('api.pixabay_client.requests.get')
    def test_search_videos_success(self, mock_get: Mock) -> None:
        """Test successful video search."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "hits": [
                {
                    "id": 12345,
                    "videos": {
                        "medium": {"url": "https://test.com/video1.mp4"},
                        "small": {"url": "https://test.com/video1_small.mp4"}
                    },
                    "tags": "nature, landscape",
                    "duration": 30
                }
            ],
            "total": 1
        }
        mock_get.return_value = mock_response
        
        # Test search
        query = "nature"
        results = self.client.search_videos(query=query, per_page=5)
        
        # Assertions
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], 12345)
        self.assertIn("videos", results[0])
        
        # Check request parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertIn("key=" + self.api_key, call_args[0][0])
        self.assertIn("q=" + query, call_args[0][0])
        
    @patch('api.pixabay_client.requests.get')
    def test_search_images_success(self, mock_get: Mock) -> None:
        """Test successful image search."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "hits": [
                {
                    "id": 67890,
                    "webformatURL": "https://test.com/image1.jpg",
                    "tags": "city, building",
                    "views": 1500
                }
            ],
            "total": 1
        }
        mock_get.return_value = mock_response
        
        # Test search
        query = "city"
        results = self.client.search_images(query=query, per_page=3)
        
        # Assertions
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], 67890)
        self.assertIn("webformatURL", results[0])
        
    @patch('api.pixabay_client.requests.get')
    def test_search_api_error(self, mock_get: Mock) -> None:
        """Test API error handling."""
        # Mock error response
        mock_response