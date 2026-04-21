"""
Main Flask application for the multilingual AI chatbot.
Integrates DeepSeek, ElevenLabs, Pixabay, and Survey APIs.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_cors import CORS
from flask_session import Session
from dotenv import load_dotenv

# Import custom modules
from api.deepseek_client import DeepSeekClient
from api.elevenlabs_client import ElevenLabsClient
from api.pixabay_client import PixabayClient
from api.survey_client import SurveyClient
from core.chat_manager import ChatManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chatbot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ChatbotApp:
    """Main application class for the AI chatbot."""
    
    def __init__(self) -> None:
        """Initialize the Flask application and API clients."""
        self.app = Flask(__name__)
        self._configure_app()
        self._initialize_clients()
        self._register_routes()
        
    def _configure_app(self) -> None:
        """Configure Flask application settings."""
        # Security settings
        self.app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
        self.app.config['SESSION_TYPE'] = 'filesystem'
        self.app.config['SESSION_PERMANENT'] = False
        self.app.config['SESSION_USE_SIGNER'] = True
        self.app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
        
        # File upload settings
        self.app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
        self.app.config['UPLOAD_FOLDER'] = 'static/uploads'
        
        # Create upload folder if it doesn't exist
        Path(self.app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
        
        # Initialize extensions
        CORS(self.app)
        Session(self.app)
        
    def _initialize_clients(self) -> None:
        """Initialize API clients with error handling."""
        try:
            self.deepseek_client = DeepSeekClient(
                api_key=os.getenv('DEEPSEEK_API_KEY'),
                model=os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
            )
            logger.info("DeepSeek client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize DeepSeek client: {e}")
            self.deepseek_client = None
            
        try:
            self.elevenlabs_client = ElevenLabsClient(
                api_key=os.getenv('ELEVENLABS_API_KEY'),
                voice_id=os.getenv('ELEVENLABS_VOICE_ID', 'default')
            )
            logger.info("ElevenLabs client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ElevenLabs client: {e}")
            self.elevenlabs_client = None
            
        try:
            self.pixabay_client = PixabayClient(
                api_key=os.getenv('PIXABAY_API_KEY')
            )
            logger.info("Pixabay client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Pixabay client: {e}")
            self.pixabay_client = None
            
        try:
            self.survey_client = SurveyClient(
                api_key=os.getenv('SURVEY_API_KEY'),
                base_url=os.getenv('SURVEY_API_URL')
            )
            logger.info("Survey client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Survey client: {e}")
            self.survey_client = None
            
        # Initialize chat manager
        self.chat_manager = ChatManager()
        
    def _register_routes(self) -> None:
        """Register all Flask routes."""
        # Main routes
        self.app.route('/')(self.index)
        self.app.route('/chat', methods=['POST'])(self.chat)
        self.app.route('/chat/history', methods=['GET'])(self.get_chat_history)
        self.app.route('/chat/<chat_id>', methods=['GET'])(self.get_chat)
        self.app.route('/chat/<chat_id>', methods=['DELETE'])(self.delete_chat)
        self.app.route('/new-chat', methods=['POST'])(self.new_chat)
        
        # Media routes
        self.app.route('/generate-voice', methods=['POST'])(self.generate_voice)
        self.app.route('/search-media', methods=['POST'])(self.search_media)
        self.app.route('/create-video-project', methods=['POST'])(self.create_video_project)
        
        # Survey routes
        self.app.route('/survey/create', methods=['POST'])(self.create_survey)
        self.app.route('/survey/<survey_id>', methods=['GET'])(self.get_survey)
        
        # Utility routes
        self.app.route('/health', methods=['GET'])(self.health_check)
        self.app.route('/languages', methods=['GET'])(self.get_supported_languages)
        self.app.route('/config', methods=['GET'])(self.get_config)
        
        # Static file serving
        self.app.route('/uploads/<filename>')(self.serve_upload)
        
    def index(self) -> str:
        """Render the main chat interface."""
        return render_template('index.html')
        
    def chat(self) -> Dict[str, Any]:
        """
        Handle chat messages from the user.
        
        Returns:
            JSON response with chat completion
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
                
            message = data.get('message', '').strip()
            chat_id = data.get('chat_id')
            language = data.get('language', 'auto')
            
            if not message:
                return jsonify({'error': 'Message is required'}), 400
                
            # Detect language if auto
            if language == 'auto':
                language = self.chat_manager.detect_language(message)
                
            # Get or create chat session
            if not chat_id:
                chat_id = self.chat_manager.create_chat_session()
                
            # Add user message to chat history
            self.chat_manager.add_message(chat_id, 'user', message, language)
            
            # Generate response using DeepSeek
            if not self.deepseek_client:
                return jsonify({'error': 'DeepSeek service unavailable'}), 503
                
            # Prepare context from chat history
            context = self.chat_manager.get_chat_context(chat_id)
            
            # Generate AI response
            ai_response = self.deepseek_client.generate_response(
                message=message,
                context=context,
                language=language
            )
            
            # Add AI response to chat history
            self.chat_manager.add_message(chat_id, 'assistant', ai_response, language)
            
            # Check if response contains code or project instructions
            response_data = {
                'message': ai_response,
                'chat_id': chat_id,
                'language': language,
                'timestamp': datetime.now().isoformat()
            }
            
            # Check for code generation requests
            if any(keyword in message.lower() for keyword in ['code', 'program', 'create', 'build', 'project']):
                response_data['has_code'] = True
                
            # Check for media requests
            if any(keyword in message.lower() for keyword in ['video', 'image', 'picture', 'media']):
                response_data['needs_media'] = True
                
            return jsonify(response_data)
            
        except Exception as e:
            logger.error(f"Error in chat endpoint: {e}")
            return jsonify({'error': str(e)}), 500
            
    def get_chat_history(self) -> Dict[str, Any]:
        """
        Get all chat sessions for the current user.
        
        Returns:
            JSON response with chat history
        """
        try:
            chats = self.chat_manager.get_all_chats()
            return jsonify({'chats': chats})
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return jsonify({'error': str(e)}), 500
            
    def get_chat(self, chat_id: str) -> Dict[str, Any]:
        """
        Get specific chat session by ID.
        
        Args:
            chat_id: Unique identifier for the chat session
            
        Returns:
            JSON response with chat messages
        """
        try:
            chat = self.chat_manager.get_chat(chat_id)
            if not chat:
                return jsonify({'error': 'Chat not found'}), 404
            return jsonify(chat)
        except Exception as e:
            logger.error(f"Error getting chat {chat_id}: {e}")
            return jsonify({'error': str(e)}), 500
            
    def delete_chat(self, chat_id: str) -> Dict[str, Any]:
        """
        Delete a chat session.
        
        Args:
            chat_id: Unique identifier for the chat session
            
        Returns:
            JSON response with success status
        """
        try:
            success = self.chat_manager.delete_chat(chat_id)
            if not success:
                return jsonify({'error': 'Chat not found'}), 404
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error deleting chat {chat_id}: {e}")
            return jsonify({'error': str(e)}), 500
            
    def new_chat(self) -> Dict[str, Any]:
        """
        Create a new chat session.
        
        Returns:
            JSON response with new chat ID
        """
        try:
            data = request.get_json() or {}
            title = data.get('title', 'New Chat')
            
            chat_id = self.chat_manager.create_chat_session(title=title)
            return jsonify({'chat_id': chat_id, 'title': title})
        except Exception as e:
            logger.error(f"Error creating new chat: {e}")
            return jsonify({'error': str(e)}), 500
            
    def generate_voice(self) -> Dict[str, Any]:
        """
        Generate voice audio from text.
        
        Returns:
            JSON response with audio file URL or error
        """
        try:
            if not self.elevenlabs_client:
                return jsonify({'error': 'Voice service unavailable'}), 503
                
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
                
            text = data.get('text', '').strip()
            language = data.get('language', 'en')
            
            if not text:
                return jsonify({'error': 'Text is required'}), 400
                
            # Generate audio
            audio_data = self.elevenlabs_client.text_to_speech(text, language)
            
            # Save audio file
            filename = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            filepath = Path(self.app.config['UPLOAD_FOLDER']) / filename