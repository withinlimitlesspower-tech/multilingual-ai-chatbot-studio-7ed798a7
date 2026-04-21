"""
Main Flask application for the AI Chatbot with multi-API integration.
"""

import os
import logging
from typing import Dict, Any, Optional
from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_cors import CORS
from flask_session import Session
from datetime import datetime
import json

# Import custom modules
from api.deepseek_client import DeepSeekClient
from api.elevenlabs_client import ElevenLabsClient
from api.pixabay_client import PixabayClient
from api.survey_client import SurveyClient
from core.chat_manager import ChatManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app() -> Flask:
    """
    Create and configure the Flask application.
    
    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_FILE_DIR'] = './flask_session'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    
    # Initialize extensions
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    Session(app)
    
    # Initialize API clients
    try:
        deepseek_client = DeepSeekClient()
        elevenlabs_client = ElevenLabsClient()
        pixabay_client = PixabayClient()
        survey_client = SurveyClient()
        chat_manager = ChatManager(
            deepseek_client=deepseek_client,
            elevenlabs_client=elevenlabs_client,
            pixabay_client=pixabay_client,
            survey_client=survey_client
        )
        logger.info("All API clients initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize API clients: {e}")
        raise
    
    @app.route('/')
    def index() -> str:
        """
        Serve the main chat interface.
        
        Returns:
            str: Rendered HTML template
        """
        return render_template('index.html')
    
    @app.route('/static/<path:filename>')
    def serve_static(filename: str) -> Any:
        """
        Serve static files.
        
        Args:
            filename (str): Path to static file
            
        Returns:
            Any: Static file response
        """
        return send_from_directory('static', filename)
    
    @app.route('/api/chat', methods=['POST'])
    def chat() -> Any:
        """
        Handle chat messages from the user.
        
        Returns:
            Any: JSON response with chat result
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            message = data.get('message', '').strip()
            session_id = data.get('session_id') or session.get('session_id')
            
            if not message:
                return jsonify({'error': 'Message is required'}), 400
            
            # Generate session ID if not exists
            if not session_id:
                session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"
                session['session_id'] = session_id
            
            logger.info(f"Processing chat message for session {session_id}")
            
            # Process chat message
            response = chat_manager.process_message(
                message=message,
                session_id=session_id,
                user_id=session.get('user_id', 'anonymous')
            )
            
            return jsonify({
                'success': True,
                'response': response,
                'session_id': session_id
            })
            
        except Exception as e:
            logger.error(f"Error in chat endpoint: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/chat/history', methods=['GET'])
    def get_chat_history() -> Any:
        """
        Get chat history for current session.
        
        Returns:
            Any: JSON response with chat history
        """
        try:
            session_id = request.args.get('session_id') or session.get('session_id')
            if not session_id:
                return jsonify({'history': []})
            
            history = chat_manager.get_chat_history(session_id)
            return jsonify({
                'success': True,
                'history': history
            })
            
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/chat/sessions', methods=['GET'])
    def get_chat_sessions() -> Any:
        """
        Get list of chat sessions.
        
        Returns:
            Any: JSON response with sessions list
        """
        try:
            sessions = chat_manager.get_sessions()
            return jsonify({
                'success': True,
                'sessions': sessions
            })
            
        except Exception as e:
            logger.error(f"Error getting chat sessions: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/chat/clear', methods=['POST'])
    def clear_chat() -> Any:
        """
        Clear chat history for current session.
        
        Returns:
            Any: JSON response indicating success
        """
        try:
            data = request.get_json() or {}
            session_id = data.get('session_id') or session.get('session_id')
            
            if session_id:
                chat_manager.clear_chat_history(session_id)
                logger.info(f"Cleared chat history for session {session_id}")
            
            return jsonify({'success': True})
            
        except Exception as e:
            logger.error(f"Error clearing chat: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/voice/synthesize', methods=['POST'])
    def synthesize_voice() -> Any:
        """
        Synthesize text to speech.
        
        Returns:
            Any: JSON response with audio data or URL
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            text = data.get('text', '').strip()
            if not text:
                return jsonify({'error': 'Text is required'}), 400
            
            voice_id = data.get('voice_id', 'default')
            
            # Synthesize speech
            audio_data = elevenlabs_client.synthesize_speech(text, voice_id)
            
            return jsonify({
                'success': True,
                'audio_data': audio_data
            })
            
        except Exception as e:
            logger.error(f"Error synthesizing voice: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/media/search', methods=['GET'])
    def search_media() -> Any:
        """
        Search for images and videos.
        
        Returns:
            Any: JSON response with media results
        """
        try:
            query = request.args.get('query', '').strip()
            media_type = request.args.get('type', 'all')
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 20))
            
            if not query:
                return jsonify({'error': 'Search query is required'}), 400
            
            # Search media
            results = pixabay_client.search_media(
                query=query,
                media_type=media_type,
                page=page,
                per_page=per_page
            )
            
            return jsonify({
                'success': True,
                'results': results
            })
            
        except Exception as e:
            logger.error(f"Error searching media: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/survey/create', methods=['POST'])
    def create_survey() -> Any:
        """
        Create a new survey.
        
        Returns:
            Any: JSON response with survey details
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            title = data.get('title', '').strip()
            questions = data.get('questions', [])
            
            if not title or not questions:
                return jsonify({'error': 'Title and questions are required'}), 400
            
            # Create survey
            survey = survey_client.create_survey(title, questions)
            
            return jsonify({
                'success': True,
                'survey': survey
            })
            
        except Exception as e:
            logger.error(f"Error creating survey: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/project/generate', methods=['POST'])
    def generate_project() -> Any:
        """
        Generate code for a video studio project or other programming task.
        
        Returns:
            Any: JSON response with generated project code
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            description = data.get('description', '').strip()
            project_type = data.get('type', 'video_studio')
            language = data.get('language', 'python')
            
            if not description:
                return jsonify({'error': 'Project description is required'}), 400
            
            # Generate project code using DeepSeek
            prompt = f"""
            Generate complete {language} code for a {project_type} project.
            
            Project requirements:
            {description}
            
            Provide:
            1. Complete working code
            2. File structure
            3. Dependencies if any
            4. Setup instructions
            5. Usage examples
            
            Make sure the code is production-ready and well-documented.
            """
            
            response = deepseek_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=4000
            )
            
            return jsonify({
                'success': True,
                'project': {
                    'type': project_type,
                    'language': language,
                    'code': response,
                    'timestamp': datetime.now().isoformat()
                }
            })
            
        except Exception as e:
            logger.error(f"Error generating project: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/health', methods=['GET'])
    def health_check() -> Any:
        """
        Health check endpoint.
        
        Returns:
            Any: JSON response with health status
        """
        try:
            # Check all services
            services = {
                'deepseek': deepseek_client.check_health(),
                'elevenlabs': elevenlabs_client.check_health(),
                '