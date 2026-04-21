"""
Main application entry point for AI Chatbot with multimodal capabilities.
Integrates DeepSeek API, ElevenLabs voice, Pixabay media, and survey functionality.
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_cors import CORS
from flask_session import Session
from dotenv import load_dotenv

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

# Initialize Flask app
app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

# Configuration
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production'),
    SESSION_TYPE='filesystem',
    SESSION_PERMANENT=False,
    SESSION_USE_SIGNER=True,
    SESSION_FILE_DIR='./flask_session',
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16MB max upload
    JSON_AS_ASCII=False  # Support non-ASCII characters
)

# Enable CORS for API routes
CORS(app, resources={
    r"/api/*": {
        "origins": os.getenv('ALLOWED_ORIGINS', '*').split(',')
    }
})

# Initialize session
Session(app)

# Ensure directories exist
Path('static/uploads').mkdir(parents=True, exist_ok=True)
Path('static/audio').mkdir(parents=True, exist_ok=True)
Path('flask_session').mkdir(parents=True, exist_ok=True)

# Import API clients (circular imports avoided)
from api_clients.deepseek_client import DeepSeekClient
from api_clients.elevenlabs_client import ElevenLabsClient
from api_clients.pixabay_client import PixabayClient
from api_clients.survey_client import SurveyClient
from utils.language_detector import LanguageDetector
from utils.code_generator import CodeGenerator

# Initialize API clients
deepseek_client = None
elevenlabs_client = None
pixabay_client = None
survey_client = None
language_detector = None
code_generator = None

def initialize_clients() -> None:
    """Initialize all API clients with environment configuration."""
    global deepseek_client, elevenlabs_client, pixabay_client, survey_client
    global language_detector, code_generator
    
    try:
        # DeepSeek API client
        deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
        if not deepseek_api_key:
            logger.warning("DeepSeek API key not found in environment variables")
        deepseek_client = DeepSeekClient(
            api_key=deepseek_api_key,
            model="deepseek-chat",
            base_url="https://api.deepseek.com"
        )
        
        # ElevenLabs API client
        elevenlabs_api_key = os.getenv('ELEVENLABS_API_KEY')
        if elevenlabs_api_key:
            elevenlabs_client = ElevenLabsClient(
                api_key=elevenlabs_api_key,
                voice_id=os.getenv('ELEVENLABS_VOICE_ID', 'default')
            )
        
        # Pixabay API client
        pixabay_api_key = os.getenv('PIXABAY_API_KEY')
        if pixabay_api_key:
            pixabay_client = PixabayClient(api_key=pixabay_api_key)
        
        # Survey API client
        survey_api_key = os.getenv('SURVEY_API_KEY')
        survey_base_url = os.getenv('SURVEY_BASE_URL', 'https://api.surveymonkey.com/v3')
        if survey_api_key:
            survey_client = SurveyClient(
                api_key=survey_api_key,
                base_url=survey_base_url
            )
        
        # Language detector
        language_detector = LanguageDetector()
        
        # Code generator
        code_generator = CodeGenerator()
        
        logger.info("All API clients initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize API clients: {str(e)}")
        raise

# Initialize clients on app startup
with app.app_context():
    initialize_clients()

@app.before_request
def before_request() -> None:
    """Execute before each request."""
    session.permanent = True
    app.permanent_session_lifetime = 3600  # 1 hour
    
    # Initialize session variables if not present
    if 'chat_history' not in session:
        session['chat_history'] = []
    if 'user_id' not in session:
        session['user_id'] = f"user_{datetime.now().timestamp()}"
    if 'language_preference' not in session:
        session['language_preference'] = 'auto'

@app.route('/')
def index() -> str:
    """Render the main chat interface."""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat() -> Dict[str, Any]:
    """
    Handle chat messages with AI processing.
    
    Returns:
        JSON response with AI reply and optional media
    """
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({
                'error': 'Message is required',
                'success': False
            }), 400
        
        user_message = data['message'].strip()
        user_id = session.get('user_id')
        language_preference = data.get('language', session.get('language_preference', 'auto'))
        
        # Detect language if auto
        if language_preference == 'auto':
            detected_lang = language_detector.detect(user_message)
            session['language_preference'] = detected_lang
        else:
            detected_lang = language_preference
        
        logger.info(f"Chat request from {user_id}: {user_message[:50]}... (Language: {detected_lang})")
        
        # Check if this is a code generation request
        is_code_request = code_generator.is_code_generation_request(user_message)
        
        # Prepare context from chat history
        chat_history = session.get('chat_history', [])
        context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-5:]])
        
        # Generate AI response
        if is_code_request:
            ai_response = code_generator.generate_code(
                prompt=user_message,
                language=detected_lang,
                context=context
            )
            response_type = 'code'
        else:
            ai_response = deepseek_client.chat_completion(
                message=user_message,
                context=context,
                language=detected_lang
            )
            response_type = 'text'
        
        # Generate voice if requested and client available
        voice_url = None
        if data.get('generate_voice', False) and elevenlabs_client:
            try:
                voice_url = elevenlabs_client.text_to_speech(
                    text=ai_response,
                    language=detected_lang
                )
            except Exception as e:
                logger.error(f"Voice generation failed: {str(e)}")
        
        # Search for relevant media if requested
        media_results = None
        if data.get('search_media', False) and pixabay_client:
            try:
                media_results = pixabay_client.search_media(
                    query=user_message,
                    media_type=data.get('media_type', 'all'),
                    per_page=5
                )
            except Exception as e:
                logger.error(f"Media search failed: {str(e)}")
        
        # Update chat history
        chat_history.append({
            'role': 'user',
            'content': user_message,
            'timestamp': datetime.now().isoformat(),
            'language': detected_lang
        })
        
        chat_history.append({
            'role': 'assistant',
            'content': ai_response,
            'timestamp': datetime.now().isoformat(),
            'type': response_type,
            'voice_url': voice_url,
            'media_results': media_results
        })
        
        # Keep only last 50 messages
        if len(chat_history) > 50:
            chat_history = chat_history[-50:]
        
        session['chat_history'] = chat_history
        
        # Prepare response
        response_data = {
            'success': True,
            'response': ai_response,
            'type': response_type,
            'language': detected_lang,
            'timestamp': datetime.now().isoformat()
        }
        
        if voice_url:
            response_data['voice_url'] = voice_url
        
        if media_results:
            response_data['media_results'] = media_results
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/chat/history', methods=['GET'])
def get_chat_history() -> Dict[str, Any]:
    """Retrieve user's chat history."""
    try:
        chat_history = session.get('chat_history', [])
        
        return jsonify({
            'success': True,
            'history': chat_history,
            'count': len(chat_history)
        })
        
    except Exception as e:
        logger.error(f"Failed to get chat history: {str(e)}")
        return jsonify({
            'error': 'Failed to retrieve chat history',
            'success': False
        }), 500

@app.route('/api/chat/clear', methods=['POST'])
def clear_chat_history() -> Dict[str, Any]:
    """Clear user's chat history."""
    try:
        session['chat_history'] = []
        
        return jsonify({
            'success': True,
            'message': 'Chat history cleared'
        })
        
    except Exception as e:
        logger.error(f"Failed to clear chat history: {str(e)}")
        return jsonify({
            'error': 'Failed to clear chat history',
            'success': False
        }), 500

@app.route('/api/survey', methods=['POST'])
def create_survey() -> Dict[str, Any]:
    """Create a new survey based on user request."""
    try:
        if not survey_client:
            return jsonify({
                'error': 'Survey functionality not available',
                'success': False
            }), 503
        
        data = request.get_json()
        
        if not data or 'topic' not in data:
            return jsonify({
                'error': 'Survey topic is required',
                'success': False
            }), 400
        
        survey_data = survey_client.create_survey(
            title=data['topic'],
            questions=data.get('questions', []),
            description=data.get('description', '')
        )
        
        return jsonify({
            'success': True,
            'survey': survey_data
        })
        
    except Exception as e:
        logger.error(f"Survey creation error: {str(e)}")
        return jsonify({
            'error': 'Failed to create survey',
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/media/search', methods=['GET'])
def search_media() -> Dict[str, Any]:
    """Search for images and videos."""
    try:
        if not pixabay_client:
            return jsonify({
                'error': 'Media search not available',
                'success': False
            }), 503
        
        query = request.args.get('q', '')
        media_type = request.args.get('type', 'all')
        per_page = int(request.args.get('per_page', 10))
        
        if not query:
            return jsonify({
                'error': 'Search query is required',
                'success': False
            }), 400
        
        results = pixabay_client.search_media(
            query=query,
            media_type=media_type,
            per_page=per_page
        )
        
        return jsonify({
            'success': True,
            'query': query,
            'results': results,
            'count': len(results)
        })
        
    except Exception as e:
        logger.error(f"Media search error: {str(e)}")
        return jsonify({
            'error': 'Failed to search media',
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/voice/generate', methods=['POST'])
def generate_voice() -> Dict[str, Any]:
    """Generate voice from text."""
    try:
        if not elevenlabs_client:
            return jsonify({
                'error': 'Voice generation not available',
                'success': False
            }), 503
        
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({
                'error': 'Text is required for voice generation',
                'success': False
            }), 400
        
        voice_url = elevenlabs_client.text_to_speech(
            text=data['text'],
            language=data.get('language', 'en'),
            voice_id=data.get('voice_id')
        )
        
        return jsonify({
            'success': True,
            'voice_url': voice_url
        })
        
    except Exception as e:
        logger.error(f"Voice generation error: {str(e)}")
        return jsonify({
            'error': 'Failed to generate voice',
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    try:
        services = {
            'deepseek': deepseek_client is not None,
            'elevenlabs': elevenlabs_client is not None,
            'pixabay': pixabay_client is not None,
            'survey': survey_client is not None,
            'language_detector': language_detector is not None,
            'code_generator': code_generator is not None
        }
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': services,
            'session_id': session.get('user_id')
        })
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@app.route('/static/<path:filename>')
def serve_static(filename: str) -> Any:
    """Serve static files."""
    return send_from_directory(app.static_folder, filename)

@app.errorhandler(404)
def not_found(error) -> Dict[str, Any]:
    """Handle 404 errors."""
    return jsonify({
        'error': 'Endpoint not found',
        'success': False
    }), 404

@app.errorhandler(405)
def method_not_allowed(error) -> Dict[str, Any]:
    """Handle 405 errors."""
    return jsonify({
        'error': 'Method not allowed',
        'success': False
    }), 405

@app.errorhandler(500)
def internal_error(error) -> Dict[str, Any]:
    """Handle 500 errors."""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        'error': 'Internal server error',
        'success': False
    }), 500

if __name__ == '__main__':
    # Get port from environment variable or default
    port = int(os.getenv('PORT', 5000))
    
    # Run the app
    app.run(
        host='0.0.0.0',
        port=port,
        debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    )