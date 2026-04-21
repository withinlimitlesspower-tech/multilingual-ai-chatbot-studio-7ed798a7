-- data/schema.sql
-- SQL Schema for Gemini-like Chatbot with Multilingual Support
-- Supports chat history, user data, tasks, media, and surveys

-- Enable UUID extension for unique identifiers
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table for storing user information
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    language_preference VARCHAR(10) DEFAULT 'en',
    voice_preference VARCHAR(50) DEFAULT 'default',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    CONSTRAINT valid_language CHECK (language_preference IN ('en', 'ur', 'hi', 'roman_en'))
);

-- Chat sessions table for grouping messages
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL DEFAULT 'New Chat',
    session_type VARCHAR(50) DEFAULT 'general',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Messages table for storing chat history
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    tokens_used INTEGER DEFAULT 0,
    audio_file_path VARCHAR(500),
    video_file_path VARCHAR(500),
    image_file_path VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- User tasks table for tracking programming/code generation tasks
CREATE TABLE IF NOT EXISTS user_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    task_type VARCHAR(50) NOT NULL CHECK (task_type IN ('code_generation', 'video_project', 'image_search', 'survey', 'voice_generation')),
    prompt TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    generated_code TEXT,
    generated_files JSONB DEFAULT '[]'::jsonb,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Media files table for storing references to Pixabay and generated media
CREATE TABLE IF NOT EXISTS media_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    media_type VARCHAR(20) NOT NULL CHECK (media_type IN ('image', 'video', 'audio')),
    source VARCHAR(50) NOT NULL CHECK (source IN ('pixabay', 'elevenlabs', 'generated', 'uploaded')),
    file_url VARCHAR(500) NOT NULL,
    file_path VARCHAR(500),
    thumbnail_url VARCHAR(500),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Survey responses table
CREATE TABLE IF NOT EXISTS survey_responses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    survey_id VARCHAR(100) NOT NULL,
    question TEXT NOT NULL,
    response TEXT NOT NULL,
    response_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- API usage tracking table
CREATE TABLE IF NOT EXISTS api_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    api_name VARCHAR(50) NOT NULL CHECK (api_name IN ('deepseek', 'elevenlabs', 'pixabay', 'survey')),
    endpoint VARCHAR(255),
    tokens_used INTEGER DEFAULT 0,
    credits_used DECIMAL(10,4) DEFAULT 0,
    response_time_ms INTEGER,
    status_code INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_tasks_user_id ON user_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_user_tasks_status ON user_tasks(status);
CREATE INDEX IF NOT EXISTS idx_media_files_user_id ON media_files(user_id);
CREATE INDEX IF NOT EXISTS idx_media_files_media_type ON media_files(media_type);
CREATE INDEX IF NOT EXISTS idx_survey_responses_user_id ON survey_responses(user_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_user_id ON api_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_created_at ON api_usage(created_at);

-- Full-text search index for message content
CREATE INDEX IF NOT EXISTS idx_messages_content_search ON messages USING gin(to_tsvector('english', content));

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for automatic updated_at updates
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chat_sessions_updated_at 
    BEFORE UPDATE ON chat_sessions 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Function to get user chat statistics
CREATE OR REPLACE FUNCTION get_user_chat_stats(user_uuid UUID)
RETURNS TABLE(
    total_sessions BIGINT,
    total_messages BIGINT,
    total_tokens BIGINT,
    favorite_language VARCHAR(10),
    last_active TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(DISTINCT cs.id)::BIGINT as total_sessions,
        COUNT(m.id)::BIGINT as total_messages,
        COALESCE(SUM(m.tokens_used), 0)::BIGINT as total_tokens,
        COALESCE(mode() WITHIN GROUP (ORDER BY m.language), 'en') as favorite_language,
        MAX(m.created_at) as last_active
    FROM users u
    LEFT JOIN chat_sessions cs ON u.id = cs.user_id
    LEFT JOIN messages m ON cs.id = m.session_id
    WHERE u.id = user_uuid
    GROUP BY u.id;
END;
$$ LANGUAGE plpgsql;

-- View for active chat sessions with message counts
CREATE OR REPLACE VIEW active_chat_sessions AS
SELECT 
    cs.id,
    cs.title,
    cs.user_id,
    u.username,
    COUNT(m.id) as message_count,
    MAX(m.created_at) as last_message_at,
    cs.created_at,
    cs.updated_at
FROM chat_sessions cs
JOIN users u ON cs.user_id = u.id
LEFT JOIN messages m ON cs.id = m.session_id
WHERE cs.is_active = TRUE
GROUP BY cs.id, cs.title, cs.user_id, u.username, cs.created_at, cs.updated_at
ORDER BY cs.updated_at DESC;

-- Insert default system user
INSERT INTO users (id, username, email, language_preference, is_active) 
VALUES ('00000000-0000-0000-0000-000000000000', 'system', 'system@chatbot.com', 'en', FALSE)
ON CONFLICT (id) DO NOTHING;

-- Create audit log table for security and debugging
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id UUID,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);

-- Create settings table for user preferences
CREATE TABLE IF NOT EXISTS user_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    theme VARCHAR(20) DEFAULT 'light',
    auto_save_chats BOOLEAN DEFAULT TRUE,
    max_tokens_per_message INTEGER DEFAULT 1000,
    voice_speed DECIMAL(3,2) DEFAULT 1.0,
    voice_pitch DECIMAL(3,2) DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER update_user_settings_updated_at 
    BEFORE UPDATE ON user_settings 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Create table for code templates and examples
CREATE TABLE IF NOT EXISTS code_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_name VARCHAR(100) NOT NULL,
    language VARCHAR(50) NOT NULL,
    category VARCHAR(50),
    template_code TEXT NOT NULL,
    description TEXT,
    tags TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert some default code templates
INSERT INTO code_templates (template_name, language, category, template_code, description, tags) VALUES
('video_player_basic', 'html', 'video_project', '<!DOCTYPE html>
<html>
<head>
    <title>Video Player</title>
    <style>
        .video-container { max-width: 800px; margin: 0 auto; }
        video { width: 100%; }
    </style>
</head>
<body>
    <div class="video-container">
        <video controls>
            <source src="{{video_url}}" type="video/mp4">
            Your browser does not support the video tag.
        </video>
    </div>
</body>
</html>', 'Basic HTML5 video player template', '{"html", "video", "player"}'),
('python_flask_api', 'python', 'backend', 'from flask import Flask, jsonify, request
app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({"