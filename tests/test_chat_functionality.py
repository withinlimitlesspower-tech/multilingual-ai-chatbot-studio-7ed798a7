"""
Main Flask application for the AI Chatbot with multimedia capabilities.
"""

import os
import logging
from typing import Dict, Any, Optional
from flask import Flask, render_template, request, jsonify, session, send_file
from flask_cors import CORS
from flask_session import Session
from dotenv import load_dotenv

# Import custom modules
from api.deepseek_client import DeepSeekClient
from api.elevenlabs_client import ElevenLabsClient
from api.pixabay_client import PixabayClient
from api.survey_client import SurveyClient
from core.chat_manager import ChatManager
from core.media_handler import MediaHandler
from core.code_generator import CodeGenerator
from core.multilingual_processor import MultilingualProcessor
from models.chat_session import ChatSession
from models.user_task import UserTask
from utils.helpers import validate_api_keys, sanitize_input
from utils.error_handler import handle_error, ChatbotError

# Load environment variables
load_dotenv()

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
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production'),
        SESSION_TYPE='filesystem',
        SESSION_PERMANENT=False,
        SESSION_USE_SIGNER=True,
        MAX_CONTENT_LENGTH=16 * 1024 * 1024  # 16MB max file size
    )
    
    # Initialize extensions
    CORS(app, supports_credentials=True)
    Session(app)
    
    # Initialize API clients
    try:
        deepseek_client = DeepSeekClient(
            api_key=os.getenv('DEEPSEEK_API_KEY'),
            model=os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        )
        
        elevenlabs_client = ElevenLabsClient(
            api_key=os.getenv('ELEVENLABS_API_KEY'),
            voice_id=os.getenv('ELEVENLABS_VOICE_ID', '21m00Tcm4TlvDq8ikWAM')
        )
        
        pixabay_client = PixabayClient(
            api_key=os.getenv('PIXABAY_API_KEY')
        )
        
        survey_client = SurveyClient(
            api_key=os.getenv('SURVEY_API_KEY'),
            base_url=os.getenv('SURVEY_API_URL')
        )
        
    except Exception as e:
        logger.error(f"Failed to initialize API clients: {e}")
        raise
    
    # Initialize core components
    multilingual_processor = MultilingualProcessor()
    media_handler = MediaHandler(pixabay_client, elevenlabs_client)
    code_generator = CodeGenerator(deepseek_client)
    chat_manager = ChatManager(
        deepseek_client=deepseek_client,
        media_handler=media_handler,
        code_generator=code_generator,
        multilingual_processor=multilingual_processor
    )
    
    @app.before_request
    def before_request() -> None:
        """
        Initialize session variables before each request.
        """
        if 'chat_sessions' not in session:
            session['chat_sessions'] = {}
        if 'current_session_id' not in session:
            session['current_session_id'] = None
        if 'user_tasks' not in session:
            session['user_tasks'] = []
    
    @app.route('/')
    def index() -> str:
        """
        Render the main chat interface.
        
        Returns:
            str: Rendered HTML template
        """
        return render_template('index.html')
    
    @app.route('/api/chat', methods=['POST'])
    def chat() -> Dict[str, Any]:
        """
        Handle chat messages from the user.
        
        Returns:
            Dict[str, Any]: Response containing chat message and metadata
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            message = sanitize_input(data.get('message', ''))
            session_id = data.get('session_id')
            
            if not message:
                return jsonify({'error': 'Message cannot be empty'}), 400
            
            # Get or create chat session
            if session_id and session_id in session['chat_sessions']:
                chat_session = session['chat_sessions'][session_id]
            else:
                chat_session = ChatSession()
                session_id = chat_session.id
                session['chat_sessions'][session_id] = chat_session
                session['current_session_id'] = session_id
            
            # Process the message
            response = chat_manager.process_message(
                message=message,
                chat_session=chat_session
            )
            
            # Update session
            session['chat_sessions'][session_id] = chat_session
            session.modified = True
            
            return jsonify({
                'response': response['text'],
                'session_id': session_id,
                'has_media': response.get('has_media', False),
                'media_url': response.get('media_url'),
                'audio_url': response.get('audio_url'),
                'timestamp': response.get('timestamp')
            })
            
        except ChatbotError as e:
            logger.error(f"Chatbot error: {e}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Unexpected error in chat endpoint: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/sessions', methods=['GET'])
    def get_sessions() -> Dict[str, Any]:
        """
        Get all chat sessions for the current user.
        
        Returns:
            Dict[str, Any]: List of chat sessions
        """
        try:
            sessions = session.get('chat_sessions', {})
            sessions_list = []
            
            for session_id, chat_session in sessions.items():
                sessions_list.append({
                    'id': session_id,
                    'title': chat_session.title,
                    'created_at': chat_session.created_at.isoformat(),
                    'message_count': len(chat_session.messages),
                    'is_active': session_id == session.get('current_session_id')
                })
            
            return jsonify({'sessions': sessions_list})
            
        except Exception as e:
            logger.error(f"Error getting sessions: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/sessions/<session_id>', methods=['GET'])
    def get_session(session_id: str) -> Dict[str, Any]:
        """
        Get a specific chat session.
        
        Args:
            session_id: ID of the session to retrieve
            
        Returns:
            Dict[str, Any]: Session details and messages
        """
        try:
            sessions = session.get('chat_sessions', {})
            
            if session_id not in sessions:
                return jsonify({'error': 'Session not found'}), 404
            
            chat_session = sessions[session_id]
            session['current_session_id'] = session_id
            
            return jsonify({
                'id': session_id,
                'title': chat_session.title,
                'created_at': chat_session.created_at.isoformat(),
                'messages': [
                    {
                        'role': msg.role,
                        'content': msg.content,
                        'timestamp': msg.timestamp.isoformat(),
                        'has_media': msg.has_media,
                        'media_url': msg.media_url,
                        'audio_url': msg.audio_url
                    }
                    for msg in chat_session.messages
                ]
            })
            
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/sessions/<session_id>', methods=['DELETE'])
    def delete_session(session_id: str) -> Dict[str, Any]:
        """
        Delete a chat session.
        
        Args:
            session_id: ID of the session to delete
            
        Returns:
            Dict[str, Any]: Success message
        """
        try:
            sessions = session.get('chat_sessions', {})
            
            if session_id not in sessions:
                return jsonify({'error': 'Session not found'}), 404
            
            del sessions[session_id]
            session['chat_sessions'] = sessions
            
            if session.get('current_session_id') == session_id:
                session['current_session_id'] = None
            
            session.modified = True
            
            return jsonify({'message': 'Session deleted successfully'})
            
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/tasks', methods=['POST'])
    def create_task() -> Dict[str, Any]:
        """
        Create a new user task.
        
        Returns:
            Dict[str, Any]: Created task details
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            task_description = sanitize_input(data.get('description', ''))
            task_type = data.get('type', 'general')
            
            if not task_description:
                return jsonify({'error': 'Task description cannot be empty'}), 400
            
            task = UserTask(description=task_description, task_type=task_type)
            
            if 'user_tasks' not in session:
                session['user_tasks'] = []
            
            session['user_tasks'].append({
                'id': task.id,
                'description': task.description,
                'type': task.task_type,
                'created_at': task.created_at.isoformat(),
                'status': task.status
            })
            
            session.modified = True
            
            return jsonify({
                'id': task.id,
                'description': task.description,
                'type': task.task_type,
                'created_at': task.created_at.isoformat(),
                'status': task.status
            })
            
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/tasks', methods=['GET'])
    def get_tasks() -> Dict[str, Any]:
        """
        Get all user tasks.
        
        Returns:
            Dict[str, Any]: List of user tasks
        """
        try:
            tasks = session.get('user_tasks', [])
            return jsonify({'tasks': tasks})
            
        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/media/search', methods=['GET'])
    def search_media() -> Dict[str, Any]:
        """
        Search for media (images/videos) from Pixabay.
        
        Returns:
            Dict[str, Any]: Search results
        """
        try:
            query = request.args.get('query', '')
            media_type = request.args.get('type', 'image')
            
            if not query:
                return jsonify({'error': 'Search query cannot be empty'}), 400
            
            results = media_handler.search_media(query, media_type)
            
            return jsonify({
                'query': query,
                'type': media_type,