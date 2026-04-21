"""
Main Flask application for AI chatbot with multi-API integration.
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

from api.deepseek_client import DeepSeekClient
from api.elevenlabs_client import ElevenLabsClient
from api.pixabay_client import PixabayClient
from api.survey_client import SurveyClient

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


class ChatBotApp:
    """Main chatbot application class."""
    
    def __init__(self) -> None:
        """Initialize the Flask application and API clients."""
        self.app = Flask(__name__)
        self._configure_app()
        self._init_clients()
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
        self.app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
        self.app.config['UPLOAD_FOLDER'] = 'static/uploads'
        
        # Create upload folder if it doesn't exist
        Path(self.app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
        
        # Initialize extensions
        CORS(self.app)
        Session(self.app)
        
    def _init_clients(self) -> None:
        """Initialize API clients."""
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
                voice_id=os.getenv('ELEVENLABS_VOICE_ID', '21m00Tcm4TlvDq8ikWAM')
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
            
    def _register_routes(self) -> None:
        """Register all application routes."""
        
        @self.app.route('/')
        def index() -> str:
            """Render the main chat interface."""
            return render_template('index.html')
            
        @self.app.route('/api/chat', methods=['POST'])
        def chat() -> Dict[str, Any]:
            """Handle chat messages and generate responses."""
            try:
                data: Dict[str, Any] = request.get_json()
                message: str = data.get('message', '').strip()
                chat_history: List[Dict[str, str]] = data.get('history', [])
                
                if not message:
                    return jsonify({'error': 'Message is required'}), 400
                    
                if not self.deepseek_client:
                    return jsonify({'error': 'DeepSeek service unavailable'}), 503
                
                # Add system prompt for multilingual and programming support
                system_prompt = """You are a multilingual AI assistant that understands Roman English, English, Urdu, Hindi, and other languages.
                You have programming intelligence and can create code for various projects including video studio applications.
                Provide helpful, accurate responses in the user's preferred language."""
                
                # Generate response
                response: str = self.deepseek_client.chat_completion(
                    message=message,
                    history=chat_history,
                    system_prompt=system_prompt
                )
                
                # Generate voice if ElevenLabs is available
                voice_url: Optional[str] = None
                if self.elevenlabs_client and data.get('generate_voice', False):
                    try:
                        voice_url = self.elevenlabs_client.text_to_speech(response)
                    except Exception as e:
                        logger.warning(f"Failed to generate voice: {e}")
                
                # Search for relevant media if Pixabay is available
                media_results: Dict[str, Any] = {}
                if self.pixabay_client and data.get('search_media', False):
                    try:
                        media_results = self.pixabay_client.search_videos_and_images(message)
                    except Exception as e:
                        logger.warning(f"Failed to search media: {e}")
                
                return jsonify({
                    'response': response,
                    'voice_url': voice_url,
                    'media': media_results,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Chat error: {e}")
                return jsonify({'error': 'Internal server error'}), 500
                
        @self.app.route('/api/generate_code', methods=['POST'])
        def generate_code() -> Dict[str, Any]:
            """Generate code based on user requirements."""
            try:
                data: Dict[str, Any] = request.get_json()
                requirements: str = data.get('requirements', '').strip()
                language: str = data.get('language', 'python').strip()
                
                if not requirements:
                    return jsonify({'error': 'Requirements are required'}), 400
                    
                if not self.deepseek_client:
                    return jsonify({'error': 'DeepSeek service unavailable'}), 503
                
                # Create specialized prompt for code generation
                code_prompt = f"""Generate {language} code based on these requirements: {requirements}
                
                Requirements:
                1. Provide complete, runnable code
                2. Include necessary imports
                3. Add comments for clarity
                4. Handle edge cases
                5. Follow best practices for {language}
                
                If this is for a video studio project, include:
                - Video processing capabilities
                - UI components if specified
                - Export functionality
                - Error handling"""
                
                response: str = self.deepseek_client.chat_completion(
                    message=code_prompt,
                    history=[],
                    system_prompt="You are an expert software developer. Generate clean, production-ready code."
                )
                
                return jsonify({
                    'code': response,
                    'language': language,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Code generation error: {e}")
                return jsonify({'error': 'Internal server error'}), 500
                
        @self.app.route('/api/search_media', methods=['POST'])
        def search_media() -> Dict[str, Any]:
            """Search for videos and images."""
            try:
                data: Dict[str, Any] = request.get_json()
                query: str = data.get('query', '').strip()
                media_type: str = data.get('type', 'all').strip()
                
                if not query:
                    return jsonify({'error': 'Search query is required'}), 400
                    
                if not self.pixabay_client:
                    return jsonify({'error': 'Media service unavailable'}), 503
                
                results: Dict[str, Any] = self.pixabay_client.search_videos_and_images(
                    query=query,
                    media_type=media_type
                )
                
                return jsonify(results)
                
            except Exception as e:
                logger.error(f"Media search error: {e}")
                return jsonify({'error': 'Internal server error'}), 500
                
        @self.app.route('/api/text_to_speech', methods=['POST'])
        def text_to_speech() -> Dict[str, Any]:
            """Convert text to speech."""
            try:
                data: Dict[str, Any] = request.get_json()
                text: str = data.get('text', '').strip()
                
                if not text:
                    return jsonify({'error': 'Text is required'}), 400
                    
                if not self.elevenlabs_client:
                    return jsonify({'error': 'Voice service unavailable'}), 503
                
                voice_url: str = self.elevenlabs_client.text_to_speech(text)
                
                return jsonify({
                    'voice_url': voice_url,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Text-to-speech error: {e}")
                return jsonify({'error': 'Internal server error'}), 500
                
        @self.app.route('/api/surveys', methods=['GET'])
        def get_surveys() -> Dict[str, Any]:
            """Get available surveys."""
            try:
                if not self.survey_client:
                    return jsonify({'error': 'Survey service unavailable'}), 503
                
                surveys: List[Dict[str, Any]] = self.survey_client.get_surveys()
                
                return jsonify({
                    'surveys': surveys,
                    'count': len(surveys)
                })
                
            except Exception as e:
                logger.error(f"Get surveys error: {e}")
                return jsonify({'error': 'Internal server error'}), 500
                
        @self.app.route('/api/surveys/<survey_id>/submit', methods=['POST'])
        def submit_survey(survey_id: str) -> Dict[str, Any]:
            """Submit survey responses."""
            try:
                data: Dict[str, Any] = request.get_json()
                
                if not self.survey_client:
                    return jsonify({'error': 'Survey service unavailable'}), 503
                
                result: Dict[str, Any] = self.survey_client.submit_survey(
                    survey_id=survey_id,
                    responses=data
                )
                
                return jsonify(result)
                
            except Exception as e:
                logger.error(f"Submit survey error: {e}")
                return jsonify({'error': 'Internal server error'}), 500
                
        @self.app.route('/api/