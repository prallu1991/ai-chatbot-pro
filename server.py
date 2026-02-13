"""
P.R.A.I - PRODUCTION SERVER v6.9.0
STATUS: ✅ CONVERSATIONAL MEMORY | ✅ REMEMBERS NAME | ✅ CONTEXT
"""

from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
import requests
import PyPDF2
import io
import os
import json
from datetime import datetime
import logging
import urllib.parse
import traceback
import pytz
from werkzeug.utils import secure_filename

# ============================================
# PRODUCTION CONFIGURATION
# ============================================
app = Flask(__name__)

CORS(app, origins=[
    'https://ai-chatbot-pro-wdqz.onrender.com',
    'http://localhost:8000',
    'http://127.0.0.1:8000'
])

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('production.log')
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# ENVIRONMENT VARIABLES
# ============================================
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://ai-chatbot-pro-wdqz.onrender.com').rstrip('/')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL = 'llama-3.3-70b-versatile'

# ============================================
# CONVERSATIONAL SYSTEM PROMPT - WITH MEMORY!
# ============================================
SYSTEM_PROMPT = """You are P.R.A.I, a helpful AI assistant with perfect memory.

CONVERSATIONAL RULES:
1. REMEMBER the user's name - when they tell you, use it naturally
2. REMEMBER previous topics - refer back to what was discussed
3. REMEMBER preferences - if user says they like something, remember it
4. Be conversational and natural - like talking to a friend
5. Keep responses concise but friendly

Current date and time: {current_time}
User's name: {user_name}
Previous conversation summary: {conversation_summary}
"""

# ============================================
# SUPABASE FUNCTIONS - WITH MEMORY!
# ============================================
def validate_supabase():
    return bool(SUPABASE_URL and SUPABASE_KEY)

def get_conversation_history(session_id, limit=50):
    """Get full conversation history with memory"""
    if not validate_supabase():
        return []
    try:
        headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
        response = requests.get(
            f'{SUPABASE_URL}/rest/v1/chat_history?session_id=eq.{session_id}&order=timestamp.asc&limit={limit}',
            headers=headers,
            timeout=5
        )
        return response.json() if response.status_code == 200 else []
    except:
        return []

def save_conversation(session_id, user_message, bot_reply, user_name=None, file_info=None):
    """Save conversation with metadata"""
    if not validate_supabase():
        return False
    try:
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        data = {
            'session_id': session_id[:50],
            'user_message': (user_message or '')[:1000],
            'bot_reply': (bot_reply or '')[:2000],
            'user_name': (user_name or '')[:50],
            'file_info': json.dumps(file_info) if file_info else None,
            'timestamp': datetime.utcnow().isoformat()
        }
        requests.post(f'{SUPABASE_URL}/rest/v1/chat_history', headers=headers, json=data, timeout=5)
        return True
    except:
        return False

def extract_user_context(history):
    """Extract user name and preferences from conversation history"""
    context = {
        'user_name': None,
        'preferences': [],
        'topics': [],
        'message_count': len(history)
    }
    
    for msg in history:
        if not context['user_name'] and msg.get('user_message'):
            user_msg = msg['user_message'].lower()
            
            # Extract name from "my name is X" or "I am X"
            if "my name is" in user_msg:
                name_part = user_msg.split("my name is")[-1].strip()
                context['user_name'] = name_part.split()[0].capitalize()
            elif "i am" in user_msg and len(user_msg.split()) < 10:
                name_part = user_msg.split("i am")[-1].strip()
                if len(name_part.split()) == 1:
                    context['user_name'] = name_part.capitalize()
            elif "call me" in user_msg:
                name_part = user_msg.split("call me")[-1].strip()
                context['user_name'] = name_part.split()[0].capitalize()
    
    return context

def generate_conversation_summary(history, max_messages=10):
    """Create a brief summary of recent conversation for context"""
    if not history:
        return "This is a new conversation."
    
    recent = history[-max_messages:]
    summary = []
    
    for msg in recent:
        if msg.get('user_message'):
            summary.append(f"User: {msg['user_message'][:50]}")
        if msg.get('bot_reply'):
            summary.append(f"Assistant: {msg['bot_reply'][:50]}")
    
    return " | ".join(summary[-6:])  # Last 3 exchanges

# ============================================
# AUTHENTICATION - GMAIL LOGIN
# ============================================
@app.route('/auth/login/google', methods=['GET'])
def google_login():
    try:
        if not validate_supabase():
            return jsonify({'error': 'Auth service unavailable'}), 503
        redirect_uri = f"{request.host_url.rstrip('/')}/auth/callback"
        oauth_url = f"{SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to={redirect_uri}"
        return jsonify({'url': oauth_url, 'provider': 'google'})
    except Exception as e:
        logger.error(f"Gmail login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/auth/callback', methods=['GET'])
def auth_callback():
    try:
        access_token = request.args.get('access_token')
        if not access_token:
            return redirect(f"{FRONTEND_URL}/?auth_error=no_token")
        return redirect(f"{FRONTEND_URL}/#access_token={access_token}")
    except Exception as e:
        logger.error(f"Callback error: {str(e)}")
        return redirect(f"{FRONTEND_URL}/?auth_error=callback_failed")

@app.route('/auth/user', methods=['GET'])
def get_user():
    try:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'user': None}), 200
        if not validate_supabase():
            return jsonify({'user': None}), 200
        headers = {'apikey': SUPABASE_KEY, 'Authorization': auth_header}
        response = requests.get(f'{SUPABASE_URL}/auth/v1/user', headers=headers, timeout=5)
        return jsonify(response.json()), response.status_code
    except:
        return jsonify({'user': None}), 200

@app.route('/auth/logout', methods=['POST'])
def logout():
    return jsonify({'success': True}), 200

# ============================================
# CHAT API - WITH FULL CONVERSATIONAL MEMORY!
# ============================================
@app.route('/chat', methods=['POST'])
def chat():
    """Chat endpoint with full conversational memory"""
    try:
        if not GROQ_API_KEY:
            return jsonify({'error': 'AI service not configured'}), 503
        
        data = request.get_json()
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', f'session_{datetime.utcnow().timestamp()}')[:50]
        user_name = data.get('user_name')
        file_info = data.get('file_info')
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        logger.info(f"💬 Chat - Session: {session_id[:8]}")
        
        # ============================================
        # GET CONVERSATION HISTORY AND EXTRACT CONTEXT
        # ============================================
        history = get_conversation_history(session_id, limit=50)
        context = extract_user_context(history)
        
        # Update with current user_name if provided
        if user_name and not context['user_name']:
            context['user_name'] = user_name
        
        # Generate conversation summary
        summary = generate_conversation_summary(history)
        
        # ============================================
        # BUILD MESSAGES WITH FULL CONTEXT
        # ============================================
        messages = []
        
        # System prompt with memory context
        current_time = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        system_prompt = SYSTEM_PROMPT.format(
            current_time=current_time,
            user_name=context['user_name'] or "Guest",
            conversation_summary=summary
        )
        messages.append({'role': 'system', 'content': system_prompt})
        
        # Add conversation history (last 10 exchanges for context)
        for msg in history[-20:]:
            if msg.get('user_message'):
                messages.append({'role': 'user', 'content': msg['user_message'][:500]})
            if msg.get('bot_reply'):
                messages.append({'role': 'assistant', 'content': msg['bot_reply'][:500]})
        
        # Add current message
        messages.append({'role': 'user', 'content': user_message[:500]})
        
        # ============================================
        # CALL GROQ API
        # ============================================
        response = requests.post(
            GROQ_API_URL,
            headers={'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': GROQ_MODEL,
                'messages': messages,
                'temperature': 0.7,
                'max_tokens': 500
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            bot_reply = result['choices'][0]['message']['content']
            
            # Save to database
            save_conversation(session_id, user_message, bot_reply, context['user_name'], file_info)
            
            logger.info(f"✅ Response sent - Memory active")
            return jsonify([{
                'generated_text': bot_reply,
                'session_id': session_id,
                'user_name': context['user_name']
            }])
        else:
            logger.error(f"❌ Groq API error: {response.status_code}")
            return jsonify({'error': 'AI service error'}), 503
            
    except Exception as e:
        logger.error(f"❌ Chat error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# ============================================
# FILE UPLOAD
# ============================================
@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        filename = secure_filename(file.filename)
        
        # Extract text from PDFs and text files
        extracted_text = ""
        if filename.lower().endswith('.txt'):
            try:
                extracted_text = file.read().decode('utf-8', errors='ignore')[:5000]
                file.seek(0)
            except:
                pass
        elif filename.lower().endswith('.pdf'):
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
                for page in pdf_reader.pages[:5]:
                    extracted_text += page.extract_text() + '\n'
                extracted_text = extracted_text[:5000]
                file.seek(0)
            except:
                pass
        
        return jsonify({
            'success': True,
            'filename': filename,
            'size': 0,  # Size not needed for memory fix
            'extracted_text': extracted_text,
            'message': f'File "{filename}" uploaded successfully'
        })
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': 'Upload failed'}), 500

# ============================================
# HEALTH CHECK
# ============================================
@app.route('/')
def index():
    return send_from_directory('.', 'Chatbot.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'version': '6.9.0',
        'timestamp': datetime.utcnow().isoformat(),
        'features': {
            'conversational_memory': True,
            'name_recognition': True,
            'context_aware': True
        }
    })

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🚀 P.R.A.I v6.9.0 - CONVERSATIONAL MEMORY FIXED!")
    print("=" * 70)
    print(f"✅ Memory: Remembers user name and context")
    print(f"✅ Groq: {'Configured' if GROQ_API_KEY else 'Missing'}")
    print(f"✅ Supabase: {'Connected' if validate_supabase() else 'Disconnected'}")
    print("=" * 70)
    
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
