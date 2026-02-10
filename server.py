"""
AI Assistant Pro - Backend Server with Database
Database: Supabase (Free Tier)
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import PyPDF2
import io
import os
from datetime import datetime
import logging
from supabase import create_client, Client

# ============================================
# FLASK APP CONFIGURATION
# ============================================
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# SUPABASE CONFIGURATION
# ============================================
SUPABASE_URL = "https://qucokskbztplocavbxmu.supabase.co"
SUPABASE_KEY = "sb_publishable_Do17IFydWBg3_HOsHYRiCQ_yV2Km9hc"

# Initialize Supabase client
supabase: Client = None
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("✅ Supabase database connected successfully!")
except Exception as e:
    logger.error(f"❌ Supabase connection failed: {str(e)}")
    supabase = None

# ============================================
# GROQ CONFIGURATION
# ============================================
CONFIG = {
    'API_KEY': os.environ.get('GROQ_API_KEY', 'PUT_YOUR_GROQ_KEY_HERE'),
    'API_URL': 'https://api.groq.com/openai/v1/chat/completions',
    'MODEL': 'llama-3.3-70b-versatile',
    'DEFAULT_TEMPERATURE': 0.7,
    'DEFAULT_MAX_TOKENS': 250,
}

# Personality system prompts
PERSONALITIES = {
    'professional': 'Professional formal assistant',
    'casual': 'Friendly casual assistant',
    'technical': 'Technical expert assistant',
    'creative': 'Creative imaginative assistant',
    'teacher': 'Patient educational assistant'
}

# ============================================
# DATABASE FUNCTIONS
# ============================================

def save_to_database(session_id, user_message, bot_reply, personality):
    """Save conversation to Supabase database"""
    if not supabase:
        logger.warning("Database not available, skipping save")
        return False
    
    try:
        data = {
            'session_id': session_id,
            'user_message': user_message,
            'bot_reply': bot_reply,
            'personality': personality,
            'timestamp': datetime.now().isoformat()
        }
        
        response = supabase.table('chat_history').insert(data).execute()
        logger.info(f"💾 Saved to database: Session {session_id[:8]}")
        return True
        
    except Exception as e:
        logger.error(f"Database save error: {str(e)}")
        return False

def get_chat_history(session_id):
    """Get chat history from database for a session"""
    if not supabase:
        return []
    
    try:
        response = supabase.table('chat_history')\
            .select('*')\
            .eq('session_id', session_id)\
            .order('timestamp')\
            .execute()
        
        return response.data
    except Exception as e:
        logger.error(f"Database fetch error: {str(e)}")
        return []

def clear_database_history(session_id):
    """Clear chat history from database for a session"""
    if not supabase:
        return False
    
    try:
        supabase.table('chat_history')\
            .delete()\
            .eq('session_id', session_id)\
            .execute()
        
        logger.info(f"🗑️ Cleared database history for session {session_id[:8]}")
        return True
    except Exception as e:
        logger.error(f"Database clear error: {str(e)}")
        return False

# ============================================
# ROUTES
# ============================================

@app.route('/')
def index():
    return send_from_directory('.', 'Chatbot.html')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'active_sessions': 0,
        'model': CONFIG['MODEL'],
        'api_configured': CONFIG['API_KEY'] != 'PUT_YOUR_GROQ_KEY_HERE',
        'database': 'connected' if supabase else 'disconnected',
        'deployment': 'Render Ready'
    })

@app.route('/test-db', methods=['GET'])
def test_db():
    """Test if database is working"""
    if not supabase:
        return jsonify({'error': 'Supabase client not initialized'}), 500
    
    try:
        # Try a simple query
        response = supabase.table('chat_history').select('id', count='exact').execute()
        return jsonify({
            'status': 'connected',
            'message': 'Database is working!',
            'row_count': response.count or 0,
            'supabase_url': SUPABASE_URL,
            'table': 'chat_history'
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'failed',
            'supabase_url': SUPABASE_URL
        }), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get database statistics"""
    if not supabase:
        return jsonify({'error': 'Database not connected'}), 500
    
    try:
        # Count total messages
        response = supabase.table('chat_history').select('id', count='exact').execute()
        total_messages = response.count or 0
        
        # Count unique sessions
        sessions_response = supabase.table('chat_history')\
            .select('session_id', count='exact')\
            .execute()
        unique_sessions = sessions_response.count or 0
        
        return jsonify({
            'total_messages': total_messages,
            'unique_sessions': unique_sessions,
            'database_status': 'connected',
            'table_name': 'chat_history',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    try:
        # Validate API key
        if CONFIG['API_KEY'] == 'PUT_YOUR_GROQ_KEY_HERE':
            return jsonify({'error': 'API key not configured'}), 500

        # Parse request
        data = request.json
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', 'default')
        personality = data.get('personality', 'casual')
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400

        logger.info(f"💬 Chat request - Session: {session_id[:8]}, Personality: {personality}")

        # Get conversation history from database
        history = get_chat_history(session_id)
        messages = []
        
        # Add system message based on personality
        system_prompt = f"You are a {PERSONALITIES.get(personality, 'friendly')}. "
        messages.append({'role': 'system', 'content': system_prompt})
        
        # Add conversation history
        for msg in history:
            messages.append({'role': 'user', 'content': msg['user_message']})
            messages.append({'role': 'assistant', 'content': msg['bot_reply']})
        
        # Add current user message
        messages.append({'role': 'user', 'content': user_message})

        # Prepare API request
        headers = {
            'Authorization': f"Bearer {CONFIG['API_KEY']}",
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': CONFIG['MODEL'],
            'messages': messages[-10:],  # Last 10 messages for context
            'temperature': CONFIG['DEFAULT_TEMPERATURE'],
            'max_tokens': CONFIG['DEFAULT_MAX_TOKENS']
        }

        # Call Groq API
        response = requests.post(
            CONFIG['API_URL'],
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            bot_reply = result['choices'][0]['message']['content']
            
            # Save to database
            save_to_database(session_id, user_message, bot_reply, personality)
            
            logger.info(f"✅ Response saved to database")
            return jsonify([{'generated_text': bot_reply}])
        
        else:
            error_msg = f'API Error: {response.text}'
            logger.error(error_msg)
            return jsonify({'error': error_msg}), response.status_code

    except requests.exceptions.Timeout:
        logger.error('Request timeout')
        return jsonify({'error': 'AI took too long to respond'}), 504
    
    except Exception as e:
        logger.error(f'Server error: {str(e)}')
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/history/<session_id>', methods=['GET'])
def get_history(session_id):
    """Get complete chat history for a session"""
    try:
        history = get_chat_history(session_id)
        return jsonify({
            'session_id': session_id,
            'history': history,
            'count': len(history)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clear', methods=['POST'])
def clear_chat():
    """Clear chat history from database"""
    try:
        data = request.json if request.json else {}
        session_id = data.get('session_id', 'default')
        
        # Clear from database
        success = clear_database_history(session_id)
        
        return jsonify({
            'status': 'cleared' if success else 'failed',
            'session_id': session_id,
            'database_cleared': success
        })
    
    except Exception as e:
        logger.error(f'Clear error: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file uploads"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        filename = file.filename.lower()
        
        if filename.endswith('.txt'):
            text = file.read().decode('utf-8')
            return jsonify({'text': text, 'filename': file.filename})
        
        elif filename.endswith('.pdf'):
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
            text = ''
            for page in pdf_reader.pages:
                text += page.extract_text() + '\n'
            return jsonify({
                'text': text,
                'filename': file.filename,
                'pages': len(pdf_reader.pages)
            })
        
        else:
            return jsonify({'error': 'Unsupported file type'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

# ============================================
# STARTUP
# ============================================

if __name__ == '__main__':
    import os
    
    print("\n" + "=" * 70)
    print("🤖 P.R.A.I CHATBOT WITH DATABASE")
    print("=" * 70)
    print(f"📊 Model: {CONFIG['MODEL']}")
    print(f"💾 Database: {'✅ Connected' if supabase else '❌ Disconnected'}")
    print(f"🔌 API: Groq")
    print(f"🌐 URL: https://qucokskbztplocavbxmu.supabase.co")
    print("=" * 70)
    
    # Use environment variable for port
    port = int(os.environ.get('PORT', 8000))
    host = '0.0.0.0' if 'RENDER' in os.environ else '127.0.0.1'
    
    app.run(
        host=host,
        port=port,
        debug=('RENDER' not in os.environ)
    )
