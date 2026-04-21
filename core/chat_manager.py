"""
main.py - Main Flask application for the AI chatbot
Handles chat sessions, history, and conversation flow
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_session import Session
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from api.deepseek_client import DeepSeekClient
from api.elevenlabs_client import ElevenLabsClient
from config import Config, configure_logging

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
Session(app)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# For production behind a proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Initialize API clients
deepseek_client = DeepSeekClient()
elevenlabs_client = ElevenLabsClient()

# In-memory storage for chat history (in production, use a database)
chat_sessions: Dict[str, List[Dict[str, Any]]] = {}


def create_chat_session(session_id: str) -> None:
    """Create a new chat session with initial system message."""
    if session_id not in chat_sessions:
        chat_sessions[session_id] = [
            {
                "role": "system",
                "content": Config.SYSTEM_PROMPT,
                "timestamp": datetime.now().isoformat()
            }
        ]
        logger.info(f"Created new chat session: {session_id}")


def get_chat_history(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve chat history for a session."""
    if session_id in chat_sessions:
        return chat_sessions[session_id][-limit:]  # Return last N messages
    return []


def add_message_to_session(session_id: str, role: str, content: str) -> None:
    """Add a message to the chat session."""
    if session_id not in chat_sessions:
        create_chat_session(session_id)
    
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    }
    chat_sessions[session_id].append(message)
    logger.debug(f"Added {role} message to session {session_id}")


def cleanup_old_sessions(max_age_hours: int = 24) -> None:
    """Clean up old chat sessions (simplified - in production use proper session management)."""
    current_time = datetime.now()
    sessions_to_remove = []
    
    for session_id in list(chat_sessions.keys()):
        if session_id.startswith("temp_"):
            try:
                # Extract timestamp from temp session ID
                session_time_str = session_id.split("_")[1]
                session_time = datetime.fromisoformat(session_time_str)
                hours_diff = (current_time - session_time).total_seconds() / 3600
                
                if hours_diff > max_age_hours:
                    sessions_to_remove.append(session_id)
            except (IndexError, ValueError):
                sessions_to_remove.append(session_id)
    
    for session_id in sessions_to_remove:
        del chat_sessions[session_id]
        logger.info(f"Cleaned up old session: {session_id}")


@app.route('/')
def index() -> str:
    """Render the main chat interface."""
    return render_template('index.html')


@app.route('/static/<path:filename>')
def serve_static(filename: str) -> Any:
    """Serve static files."""
    return send_from_directory('static', filename)


@app.route('/api/chat', methods=['POST'])
def chat() -> Any:
    """
    Handle chat messages from the user.
    
    Returns:
        JSON response with AI reply and metadata
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        message = data.get('message', '').strip()
        session_id = data.get('session_id', '')
        use_voice = data.get('use_voice', False)
        
        if not message:
            return jsonify({"error": "Message cannot be empty"}), 400
        
        # Generate session ID if not provided
        if not session_id:
            session_id = f"temp_{datetime.now().isoformat()}"
        
        # Clean up old sessions periodically
        if len(chat_sessions) > 100:  # Arbitrary threshold
            cleanup_old_sessions()
        
        # Add user message to session
        add_message_to_session(session_id, "user", message)
        
        # Get chat history for context
        history = get_chat_history(session_id)
        
        # Get response from DeepSeek
        logger.info(f"Processing message from session {session_id}")
        ai_response = deepseek_client.chat_completion(
            messages=history,
            user_message=message
        )
        
        if not ai_response:
            return jsonify({"error": "Failed to get AI response"}), 500
        
        # Add AI response to session
        add_message_to_session(session_id, "assistant", ai_response)
        
        response_data = {
            "response": ai_response,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        # Generate voice if requested
        if use_voice and Config.ELEVENLABS_API_KEY:
            try:
                audio_data = elevenlabs_client.text_to_speech(ai_response)
                if audio_data:
                    # Save audio file (in production, use cloud storage)
                    audio_filename = f"audio_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
                    audio_path = Path("static") / "audio" / audio_filename
                    audio_path.parent.mkdir(exist_ok=True)
                    
                    with open(audio_path, "wb") as f:
                        f.write(audio_data)
                    
                    response_data["audio_url"] = f"/static/audio/{audio_filename}"
            except Exception as e:
                logger.error(f"Failed to generate voice: {str(e)}")
                # Don't fail the whole request if voice generation fails
        
        return jsonify(response_data)
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request")
        return jsonify({"error": "Invalid JSON format"}), 400
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/api/sessions', methods=['GET'])
def get_sessions() -> Any:
    """Get list of available chat sessions."""
    try:
        sessions_list = []
        for session_id, messages in chat_sessions.items():
            if messages:
                # Get last message timestamp
                last_msg = messages[-1]
                sessions_list.append({
                    "id": session_id,
                    "last_message": last_msg.get("content", "")[:100],
                    "timestamp": last_msg.get("timestamp"),
                    "message_count": len(messages)
                })
        
        return jsonify({"sessions": sessions_list})
    
    except Exception as e:
        logger.error(f"Error getting sessions: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/api/session/<session_id>', methods=['GET'])
def get_session_history(session_id: str) -> Any:
    """Get chat history for a specific session."""
    try:
        history = get_chat_history(session_id)
        return jsonify({
            "session_id": session_id,
            "messages": history
        })
    
    except Exception as e:
        logger.error(f"Error getting session history: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/api/session/<session_id>', methods=['DELETE'])
def delete_session(session_id: str) -> Any:
    """Delete a chat session."""
    try:
        if session_id in chat_sessions:
            del chat_sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return jsonify({"message": "Session deleted successfully"})
        else:
            return jsonify({"error": "Session not found"}), 404
    
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/api/health', methods=['GET'])
def health_check() -> Any:
    """Health check endpoint."""
    try:
        # Check if API clients are initialized
        deepseek_status = deepseek_client.check_health()
        elevenlabs_status = elevenlabs_client.check_health() if Config.ELEVENLABS_API_KEY else True
        
        status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "deepseek": deepseek_status,
                "elevenlabs": elevenlabs_status
            }
        }
        
        return jsonify(status)
    
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@app.route('/api/voice/settings', methods=['GET'])
def get_voice_settings() -> Any:
    """Get available voice settings."""
    try:
        if not Config.ELEVENLABS_API_KEY:
            return jsonify({"error": "ElevenLabs API not configured"}), 400
        
        voices = elevenlabs_client.get_available_voices()
        return jsonify({
            "voices": voices,
            "current_voice": Config.ELEVENLABS_VOICE_ID
        })
    
    except Exception as e:
        logger.error(f"Error getting voice settings: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route('/api/voice/settings', methods=['POST'])
def update_voice_settings() -> Any:
    """Update voice settings."""
    try:
        if not Config.ELEVENLABS_API_KEY:
            return jsonify({"error": "ElevenLabs API not configured"}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        voice_id = data.get('voice_id')
        if voice_id:
            # In production, store this in user preferences/database
            # For now, we'll just validate it exists
            voices = elevenlabs_client.get_available_voices()
            if any(v['voice_id'] == voice_id for v in voices):
                return jsonify({"message": "Voice updated successfully"})
            else:
                return jsonify({"error": "Invalid voice ID"}), 400
        
        return jsonify({"error": "Voice ID required"}), 400
    
    except Exception as e:
        logger.error(f"Error updating voice settings: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.errorhandler(404)
def not_found(error: Any) -> Any:
    """