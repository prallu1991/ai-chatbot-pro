"""
AI Assistant Pro - Backend Server with Database & Social Authentication
Database: Supabase (Free Tier)
Social Login: Google, Facebook, Outlook, LinkedIn (via Supabase OAuth)
"""

from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
import requests
import PyPDF2
import io
import os
from datetime import datetime
import logging
import urllib.parse

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
# SUPABASE CONFIGURATION - LOAD FROM ENVIRONMENT
# ============================================
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.warning("⚠️ Supabase credentials not set in environment variables!")

# ============================================
# GROQ CONFIGURATION
# ============================================
CONFIG = {
    'API_KEY': os.environ.get('GROQ_API_KEY', ''),
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
# SOCIAL LOGIN CONFIGURATION - ALL PROVIDERS
# ============================================

# Frontend URL (your Render app)
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://ai-chatbot-pro-wdqz.onrender.com')

# Map friendly names to Supabase provider names
SOCIAL_PROVIDERS = {
    'google': 'google',
    'facebook': 'facebook',
    'outlook': 'azure',      # Outlook uses Azure provider
    'linkedin': 'linkedin',
    'github': 'github',
    'twitter': 'twitter',
    'discord': 'discord'
}

# ============================================
# DATABASE FUNCTIONS (HTTP DIRECT)
# ============================================

def save_to_database(session_id, user_message, bot_reply, personality):
    """Save conversation to Supabase using direct HTTP"""
    try:
        if not SUPABASE_KEY or not SUPABASE_URL:
            logger.error("❌ Supabase credentials missing")
            return False
            
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal'
        }
        
        data = {
            'session_id': session_id,
            'user_message': user_message,
            'bot_reply': bot_reply,
            'personality': personality,
            'timestamp': datetime.now().isoformat()
        }
        
        response = requests.post(
            f'{SUPABASE_URL}/rest/v1/chat_history',
            headers=headers,
            json=data,
            timeout=5
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"💾 Saved to database: Session {session_id[:8]}")
            return True
        else:
            logger.error(f"❌ Database save failed: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        return False

def get_chat_history(session_id):
    """Get chat history from database for a session"""
    try:
        if not SUPABASE_KEY or not SUPABASE_URL:
            return []
            
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}'
        }
        
        response = requests.get(
            f'{SUPABASE_URL}/rest/v1/chat_history?session_id=eq.{session_id}&order=timestamp.asc',
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return []
            
    except Exception as e:
        logger.error(f"History error: {str(e)}")
        return []

def clear_database_history(session_id):
    """Clear chat history from database for a session"""
    try:
        if not SUPABASE_KEY or not SUPABASE_URL:
            return False
            
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Prefer': 'return=minimal'
        }
        
        response = requests.delete(
            f'{SUPABASE_URL}/rest/v1/chat_history?session_id=eq.{session_id}',
            headers=headers,
            timeout=5
        )
        
        if response.status_code in [200, 204]:
            logger.info(f"🗑️ Cleared database history for session {session_id[:8]}")
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"Clear error: {str(e)}")
        return False

# ============================================
# AUTHENTICATION ROUTES - EMAIL
# ============================================

@app.route('/auth/signup', methods=['POST'])
def signup():
    """Register new user"""
    try:
        if not SUPABASE_KEY or not SUPABASE_URL:
            return jsonify({'error': 'Supabase not configured'}), 500
            
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'email': email,
            'password': password,
            'email_confirm': True  # Auto-confirm for testing
        }
        
        response = requests.post(
            f'{SUPABASE_URL}/auth/v1/signup',
            headers=headers,
            json=payload
        )
        
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        return jsonify({'error': 'Signup failed'}), 500


@app.route('/auth/login', methods=['POST'])
def login():
    """Login existing user"""
    try:
        if not SUPABASE_KEY or not SUPABASE_URL:
            return jsonify({'error': 'Supabase not configured'}), 500
            
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'email': email,
            'password': password
        }
        
        response = requests.post(
            f'{SUPABASE_URL}/auth/v1/token?grant_type=password',
            headers=headers,
            json=payload
        )
        
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500


@app.route('/auth/user', methods=['GET'])
def get_user():
    """Get current user from token"""
    try:
        if not SUPABASE_KEY or not SUPABASE_URL:
            return jsonify({'user': None}), 200
            
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header:
            return jsonify({'user': None}), 200
        
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': auth_header
        }
        
        response = requests.get(
            f'{SUPABASE_URL}/auth/v1/user',
            headers=headers
        )
        
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        logger.error(f"Get user error: {str(e)}")
        return jsonify({'error': 'Failed to get user'}), 500


@app.route('/auth/logout', methods=['POST'])
def logout():
    """Logout user"""
    try:
        if not SUPABASE_KEY or not SUPABASE_URL:
            return jsonify({'error': 'Supabase not configured'}), 500
            
        auth_header = request.headers.get('Authorization', '')
        
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': auth_header
        }
        
        response = requests.post(
            f'{SUPABASE_URL}/auth/v1/logout',
            headers=headers
        )
        
        return jsonify({'success': True}), response.status_code
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({'error': 'Logout failed'}), 500

# ============================================
# SOCIAL LOGIN ROUTES - ALL PROVIDERS!
# ============================================

@app.route('/auth/login/<provider>', methods=['GET'])
def social_login(provider):
    """
    Redirect to Supabase OAuth for social login
    Supported providers: google, facebook, outlook, linkedin, github, twitter, discord
    """
    try:
        if not SUPABASE_KEY or not SUPABASE_URL:
            return jsonify({'error': 'Supabase not configured'}), 500
        
        # Check if provider is supported
        if provider not in SOCIAL_PROVIDERS:
            return jsonify({'error': f'Provider {provider} not supported'}), 400
        
        # Map to Supabase provider name
        supabase_provider = SOCIAL_PROVIDERS[provider]
        
        # Construct redirect URI (this endpoint will handle the callback)
        redirect_uri = f"{request.host_url.rstrip('/')}/auth/callback"
        
        # Construct Supabase OAuth URL
        oauth_url = f"{SUPABASE_URL}/auth/v1/authorize"
        params = {
            'provider': supabase_provider,
            'redirect_to': redirect_uri
        }
        
        full_url = f"{oauth_url}?{urllib.parse.urlencode(params)}"
        
        logger.info(f"🔐 Redirecting to {provider} login: {full_url}")
        
        # Return the OAuth URL for frontend to redirect
        return jsonify({
            'url': full_url,
            'provider': provider,
            'message': f'Redirecting to {provider} login...'
        })
        
    except Exception as e:
        logger.error(f"Social login error for {provider}: {str(e)}")
        return jsonify({'error': f'Failed to initiate {provider} login'}), 500


@app.route('/auth/callback', methods=['GET'])
def auth_callback():
    """
    Handle OAuth callback from Supabase
    This is where Supabase redirects after successful social login
    """
    try:
        # Get tokens from URL fragment (Supabase sends in URL params)
        access_token = request.args.get('access_token')
        refresh_token = request.args.get('refresh_token')
        
        if not access_token:
            # Try to get from fragment (if sent as hash)
            return redirect(f"{FRONTEND_URL}/?auth_error=no_token")
        
        # Get user info from Supabase
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {access_token}'
        }
        
        user_response = requests.get(
            f'{SUPABASE_URL}/auth/v1/user',
            headers=headers
        )
        
        if user_response.status_code == 200:
            user_data = user_response.json()
            email = user_data.get('email', '')
            user_id = user_data.get('id', '')
            
            logger.info(f"✅ Social login successful: {email}")
            
            # Redirect to frontend with tokens in URL fragment
            # This allows the frontend JavaScript to read the token and save it
            redirect_url = f"{FRONTEND_URL}/#access_token={access_token}"
            if refresh_token:
                redirect_url += f"&refresh_token={refresh_token}"
            
            return redirect(redirect_url)
        else:
            logger.error(f"Failed to get user info: {user_response.status_code}")
            return redirect(f"{FRONTEND_URL}/?auth_error=user_info_failed")
            
    except Exception as e:
        logger.error(f"Auth callback error: {str(e)}")
        return redirect(f"{FRONTEND_URL}/?auth_error=callback_failed")


@app.route('/auth/providers', methods=['GET'])
def list_providers():
    """List all enabled social login providers"""
    return jsonify({
        'providers': list(SOCIAL_PROVIDERS.keys()),
        'enabled': ['google', 'facebook', 'outlook', 'linkedin', 'github', 'twitter', 'discord']
    })

# ============================================
# ROUTES - CHAT & FILE UPLOAD
# ============================================

@app.route('/')
def index():
    return send_from_directory('.', 'Chatbot.html')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'model': CONFIG['MODEL'],
        'api_configured': bool(CONFIG['API_KEY']),
        'database': 'connected' if SUPABASE_KEY and SUPABASE_URL else 'disconnected',
        'auth': {
            'email': 'enabled',
            'social': list(SOCIAL_PROVIDERS.keys())
        },
        'deployment': 'Render Ready'
    })

@app.route('/test-db', methods=['GET'])
def test_db():
    """Test if database is working"""
    try:
        if not SUPABASE_KEY or not SUPABASE_URL:
            return jsonify({'error': 'Supabase not configured'}), 500
            
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}'
        }
        
        # Test insert
        test_data = {
            'session_id': 'connection_test',
            'user_message': 'Database connection test',
            'bot_reply': 'If you see this, database is working!',
            'personality': 'test',
            'timestamp': datetime.now().isoformat()
        }
        
        insert_response = requests.post(
            f'{SUPABASE_URL}/rest/v1/chat_history',
            headers=headers,
            json=test_data,
            timeout=5
        )
        
        if insert_response.status_code in [200, 201]:
            return jsonify({
                'status': 'connected',
                'message': 'Database is working!',
                'insert_status': insert_response.status_code
            })
        else:
            return jsonify({
                'status': 'failed',
                'message': f'Insert failed: {insert_response.status_code}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'failed',
            'error': str(e)
        }), 500

@app.route('/chat', methods=['POST'])
def chat():
    try:
        # Validate API key
        if not CONFIG['API_KEY']:
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
        system_prompt = f"You are a {PERSONALITIES.get(personality, 'friendly')}. Keep responses concise and helpful."
        messages.append({'role': 'system', 'content': system_prompt})
        
        # Add conversation history (last 5 exchanges)
        for msg in history[-10:]:
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
            'messages': messages[-10:],
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
            
            logger.info(f"✅ Response sent")
            return jsonify([{'generated_text': bot_reply}])
        
        else:
            error_msg = f'API Error: {response.status_code}'
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
    print("🤖 P.R.A.I CHATBOT WITH SUPABASE DATABASE + SOCIAL AUTH")
    print("=" * 70)
    print(f"📊 Model: {CONFIG['MODEL']}")
    print(f"💾 Database: {'✅ Configured' if SUPABASE_URL and SUPABASE_KEY else '❌ Missing credentials'}")
    print(f"🔑 Auth: Email + Social Login")
    print(f"🌐 Social Providers: {', '.join(SOCIAL_PROVIDERS.keys())}")
    print(f"🔌 API: {'✅ Configured' if CONFIG['API_KEY'] else '❌ Missing API key'}")
    print(f"🚀 Frontend URL: {FRONTEND_URL}")
    print("=" * 70)
    
    # Test Supabase connection
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            test_headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}'
            }
            test_response = requests.get(
                f'{SUPABASE_URL}/rest/v1/chat_history?limit=1',
                headers=test_headers,
                timeout=5
            )
            if test_response.status_code == 200:
                print("✅ Supabase connection: OK")
            else:
                print(f"⚠️ Supabase connection: HTTP {test_response.status_code}")
        except Exception as e:
            print(f"❌ Supabase connection: Failed - {str(e)}")
    else:
        print("⚠️ Supabase not configured - set SUPABASE_URL and SUPABASE_KEY env vars")
    
    print("=" * 70)
    
    # Use environment variable for port
    port = int(os.environ.get('PORT', 8000))
    host = '0.0.0.0' if 'RENDER' in os.environ else '127.0.0.1'
    
    app.run(
        host=host,
        port=port,
        debug=('RENDER' not in os.environ)
    )
