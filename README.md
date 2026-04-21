# Gemini-Style AI Chatbot with Multimodal Capabilities 🤖

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Replit](https://img.shields.io/badge/Replit-Compatible-orange.svg)

## Description

A sophisticated AI-powered chatbot built on Replit that integrates multiple APIs to provide a Gemini-like user experience. The chatbot features multimodal capabilities including text generation, voice synthesis, media search, and code generation, with support for multiple languages including Roman English, English, Urdu, and Hindi.

## Features

### 🎯 Core Capabilities
- **Multilingual Support**: Understands and responds in Roman English, English, Urdu, Hindi, and more
- **Programming Intelligence**: Generates code and creates video studio projects based on user prompts
- **Voice Integration**: Text-to-speech using ElevenLabs API
- **Media Search**: Access to Pixabay API for videos and images
- **Survey Integration**: Built-in survey functionality
- **Chat History**: Persistent sidebar for chat history and task management

### 🎨 UI Features
- Gemini-inspired interface with main chat window and sidebar
- Responsive design for various screen sizes
- Real-time chat updates
- Media preview and playback
- Code syntax highlighting

### 🔧 Technical Features
- Modular architecture with clear separation of concerns
- Environment-based configuration
- Error handling and logging
- Session management
- API rate limiting and retry logic

## Installation

### Prerequisites
- Python 3.9 or higher
- Replit account (for deployment)
- API keys for:
  - DeepSeek API
  - ElevenLabs API
  - Pixabay API
  - Survey API (optional)

### Step-by-Step Setup

1. **Clone or Create on Replit**
      # On Replit, create new Python project and upload files
   
2. **Install Dependencies**
      pip install -r requirements.txt
   
3. **Configure Environment Variables**
   Create a `.env` file in the root directory with:
      # DeepSeek API Configuration
   DEEPSEEK_API_KEY=your_deepseek_api_key_here
   DEEPSEEK_MODEL=deepseek-chat
   DEEPSEEK_BASE_URL=https://api.deepseek.com
   
   # ElevenLabs Configuration
   ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
   ELEVENLABS_VOICE_ID=default_voice_id
   ELEVENLABS_MODEL=eleven_monolingual_v1
   
   # Pixabay Configuration
   PIXABAY_API_KEY=your_pixabay_api_key_here
   
   # Survey API Configuration (optional)
   SURVEY_API_KEY=your_survey_api_key_here
   SURVEY_API_URL=https://api.surveymonkey.com/v3
   
   # Application Settings
   SECRET_KEY=your_secret_key_here
   DEBUG=False
   PORT=5000
   
4. **File Structure Verification**
   Ensure your project has the following structure:
      project-root/
   ├── main.py
   ├── config.py
   ├── requirements.txt
   ├── .env
   ├── .env.example
   ├── static/
   │   ├── css/
   │   │   └── styles.css
   │   └── js/
   │       └── app.js
   ├── templates/