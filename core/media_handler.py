"""
main.py - Flask application entry point for multimedia chatbot
"""

import os
import logging
from typing import Dict, Any, Optional
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
from config import Config

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_app() -> Flask:
    """
    Create and configure the Flask application.
    
    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(Config)
    
    # Initialize extensions
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    Session(app)
    
    # Initialize API clients
    try:
        deepseek_client = DeepSeekClient(
            api_key=os.getenv('DEEPSEEK_API_KEY'),
            base_url=os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
        )
        elevenlabs_client = ElevenLabsClient(
            api_key=os.getenv('ELEVENLABS_API_KEY'),
            voice_id=os.getenv('ELEVENLABS_VOICE_ID')
        )
        pixabay_client = PixabayClient(
            api_key=os.getenv('PIXABAY_API_KEY')
        )
        survey_client = SurveyClient(
            api_key=os.getenv('SURVEY_API_KEY'),
            base_url=os.getenv('SURVEY_BASE_URL')
        )
        
        # Initialize chat manager
        chat_manager = ChatManager(
            deepseek_client=deepseek_client,
            elevenlabs_client=elevenlabs_client,
            pixabay_client=pixabay_client,
            survey_client=survey_client
        )
        
        # Store in app context
        app.config['CHAT_MANAGER'] = chat_manager
        
        logger.info("Application initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise
    
    @app.route('/')
    def index() -> str:
        """
        Serve the main application page.
        
        Returns:
            str: Rendered HTML template
        """
        return render_template('index.html')
    
    @app.route('/static/<path:filename>')
    def serve_static(filename: str) -> Any:
        """
        Serve static files.
        
        Args:
            filename (str): Name of the static file
            
        Returns:
            Any: Static file response
        """
        return send_from_directory('static', filename)
    
    @app.route('/api/chat', methods=['POST'])
    def chat() -> Any:
        """
        Handle chat requests from the frontend.
        
        Returns:
            Any: JSON response with chat result
        """
        try:
            data: Dict[str, Any] = request.get_json()
            
            if not data or 'message' not in data:
                return jsonify({
                    'error': 'Message is required',
                    'success': False
                }), 400
            
            message: str = data['message']
            chat_history: Optional[list] = data.get('history', [])
            language: str = data.get('language', 'en')
            
            # Get chat manager from app context
            chat_manager: ChatManager = app.config['CHAT_MANAGER']
            
            # Process chat message
            response = chat_manager.process_message(
                message=message,
                chat_history=chat_history,
                language=language
            )
            
            logger.info(f"Chat processed successfully for message: {message[:50]}...")
            return jsonify({
                'success': True,
                'response': response
            })
            
        except Exception as e:
            logger.error(f"Error in chat endpoint: {str(e)}")
            return jsonify({
                'error': 'Internal server error',
                'success': False
            }), 500
    
    @app.route('/api/generate_audio', methods=['POST'])
    def generate_audio() -> Any:
        """
        Generate audio from text using ElevenLabs API.
        
        Returns:
            Any: JSON response with audio data
        """
        try:
            data: Dict[str, Any] = request.get_json()
            
            if not data or 'text' not in data:
                return jsonify({
                    'error': 'Text is required',
                    'success': False
                }), 400
            
            text: str = data['text']
            voice_id: Optional[str] = data.get('voice_id')
            
            chat_manager: ChatManager = app.config['CHAT_MANAGER']
            audio_data = chat_manager.generate_audio(text, voice_id)
            
            return jsonify({
                'success': True,
                'audio_data': audio_data
            })
            
        except Exception as e:
            logger.error(f"Error generating audio: {str(e)}")
            return jsonify({
                'error': 'Failed to generate audio',
                'success': False
            }), 500
    
    @app.route('/api/search_media', methods=['POST'])
    def search_media() -> Any:
        """
        Search for images and videos using Pixabay API.
        
        Returns:
            Any: JSON response with media results
        """
        try:
            data: Dict[str, Any] = request.get_json()
            
            if not data or 'query' not in data:
                return jsonify({
                    'error': 'Search query is required',
                    'success': False
                }), 400
            
            query: str = data['query']
            media_type: str = data.get('type', 'all')
            per_page: int = data.get('per_page', 10)
            
            chat_manager: ChatManager = app.config['CHAT_MANAGER']
            results = chat_manager.search_media(query, media_type, per_page)
            
            return jsonify({
                'success': True,
                'results': results
            })
            
        except Exception as e:
            logger.error(f"Error searching media: {str(e)}")
            return jsonify({
                'error': 'Failed to search media',
                'success': False
            }), 500
    
    @app.route('/api/create_survey', methods=['POST'])
    def create_survey() -> Any:
        """
        Create a survey using Survey API.
        
        Returns:
            Any: JSON response with survey data
        """
        try:
            data: Dict[str, Any] = request.get_json()
            
            if not data or 'questions' not in data:
                return jsonify({
                    'error': 'Survey questions are required',
                    'success': False
                }), 400
            
            questions: list = data['questions']
            title: str = data.get('title', 'New Survey')
            
            chat_manager: ChatManager = app.config['CHAT_MANAGER']
            survey_data = chat_manager.create_survey(questions, title)
            
            return jsonify({
                'success': True,
                'survey': survey_data
            })
            
        except Exception as e:
            logger.error(f"Error creating survey: {str(e)}")
            return jsonify({
                'error': 'Failed to create survey',
                'success': False
            }), 500
    
    @app.route('/api/generate_code', methods=['POST'])
    def generate_code() -> Any:
        """
        Generate code based on user prompt.
        
        Returns:
            Any: JSON response with generated code
        """
        try:
            data: Dict[str, Any] = request.get_json()
            
            if not data or 'prompt' not in data:
                return jsonify({
                    'error': 'Code generation prompt is required',
                    'success': False
                }), 400
            
            prompt: str = data['prompt']
            language: str = data.get('language', 'python')
            
            chat_manager: ChatManager = app.config['CHAT_MANAGER']
            code = chat_manager.generate_code(prompt, language)
            
            return jsonify({
                'success': True,
                'code': code
            })
            
        except Exception as e:
            logger.error(f"Error generating code: {str(e)}")
            return jsonify({
                'error': 'Failed to generate code',
                'success': False
            }), 500
    
    @app.route('/api/health', methods=['GET'])
    def health_check() -> Any:
        """
        Health check endpoint for monitoring.
        
        Returns:
            Any: JSON response with health status
        """
        try:
            chat_manager: ChatManager = app.config['CHAT_MANAGER']
            
            # Check if all services are available
            services_status = chat_manager.check_services()
            
            return jsonify({
                'status': 'healthy',
                'services': services_status,
                'success': True
            })
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'success': False
            }), 500
    
    @app.errorhandler(404)
    def not_found(error) -> Any:
        """
        Handle 404 errors.
        
        Args:
            error: The error object
            
        Returns:
            Any: JSON response for 404 error
        """
        return jsonify({
            'error': 'Endpoint not found',
            'success': False
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error) -> Any:
        """
        Handle 500 errors.
        
        Args:
            error: The error object
            
        Returns:
            Any: JSON response for 500 error
        """
        logger.error(f"Internal server error: {str(error)}")
        return jsonify({
            'error': 'Internal server error',
            'success': False
        }), 500
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    # Get port from environment variable or use default
    port = int(os.getenv('PORT', 5000))
    
    # Run the application
    app.run(
        host='0.0.0.0',
        port=port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )