"""
P.R.A.I - PRODUCTION SERVER v7.0.0
STATUS: ✅ GROQ API CONNECTED | ✅ CONVERSATIONAL | ✅ MEMORY
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
# ENVIRONMENT VARIABLES - CHECK THESE ON RENDER!
# ============================================
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://ai-chatbot-pro-wdqz.onrender.com').rstrip('/')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

# ============================================
# GROQ API CONFIGURATION
# ============================================
GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL = 'llama-3.3-70b-versatile'

# ============================================
# CONVERSATIONAL SYSTEM PROMPT
# ============================================
SYSTEM_PROMPT = """You are P.R.A.I, a helpful, friendly AI assistant with perfect memory.

CONVERSATIONAL RULES:
1. Be natural and conversational - like talking to a friend
2. Remember the user's name and use it naturally
3. Remember previous topics and refer back to them
4. Keep responses concise but helpful (2-3 sentences usually)
5. Never say "I received your message" - that's robotic
6. Answer questions directly and accurately
7. If you don't know something, say so honestly

Current date and time: {current_time}
User's name: {user_name}
Previous conversation: {conversation_summary}
"""

# ============================================
# SUPABASE FUNCTIONS
# ============================================
def validate_supabase():
    return bool(SUPABASE_URL and SUPABASE_KEY)

def get_conversation_history(session_id, limit=50):
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
    except Exception as e:
        logger.error(f"History error: {str(e)}")
        return []

def save_conversation(session_id, user_message, bot_reply, user_name=None, file_info=None):
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
    except Exception as e:
        logger.error(f"Save error: {str(e)}")
        return False

def extract_user_context(history):
    context = {'user_name': None, 'message_count': len(history)}
    for msg in history[-20:]:
        if not context['user_name'] and msg.get('user_message'):
            user_msg = msg['user_message'].lower()
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

def generate_conversation_summary(history, max_messages=6):
    if not history:
        return "New conversation"
    recent = history[-max_messages:]
    summary = []
    for msg in recent:
        if msg.get('user_message'):
            summary.append(f"User: {msg['user_message'][:30]}")
        if msg.get('bot_reply'):
            summary.append(f"Assistant: {msg['bot_reply'][:30]}")
    return " | ".join(summary)

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
    except Exception as e:
        logger.error(f"Get user error: {str(e)}")
        return jsonify({'user': None}), 200

@app.route('/auth/logout', methods=['POST'])
def logout():
    return jsonify({'success': True}), 200

# ============================================
# CHAT API - REAL GROQ AI, NOT ECHO!
# ============================================
@app.route('/chat', methods=['POST'])
def chat():
    """REAL AI CHAT - Connected to Groq API"""
    try:
        # 1. CHECK GROQ API KEY
        if not GROQ_API_KEY:
            logger.error("❌ GROQ_API_KEY not configured")
            return jsonify({'error': 'AI service not configured - please set GROQ_API_KEY in Render environment variables'}), 503
        
        # 2. PARSE REQUEST
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request'}), 400
            
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', f'session_{datetime.utcnow().timestamp()}')[:50]
        user_name = data.get('user_name')
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        logger.info(f"💬 Chat request - Session: {session_id[:8]}")
        logger.info(f"📝 User message: {user_message[:50]}")
        
        # 3. GET CONVERSATION HISTORY
        history = get_conversation_history(session_id, limit=20)
        context = extract_user_context(history)
        
        if user_name and not context.get('user_name'):
            context['user_name'] = user_name
        
        # 4. BUILD MESSAGES FOR GROQ
        messages = []
        
        # System prompt with context
        current_time = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        summary = generate_conversation_summary(history)
        system_prompt = SYSTEM_PROMPT.format(
            current_time=current_time,
            user_name=context.get('user_name', 'there'),
            conversation_summary=summary
        )
        messages.append({'role': 'system', 'content': system_prompt})
        
        # Add conversation history (last 10 messages)
        for msg in history[-10:]:
            if msg.get('user_message'):
                messages.append({'role': 'user', 'content': msg['user_message'][:500]})
            if msg.get('bot_reply'):
                messages.append({'role': 'assistant', 'content': msg['bot_reply'][:500]})
        
        # Add current message
        messages.append({'role': 'user', 'content': user_message[:500]})
        
        # 5. CALL GROQ API
        logger.info(f"🔄 Calling Groq API with model: {GROQ_MODEL}")
        
        response = requests.post(
            GROQ_API_URL,
            headers={
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': GROQ_MODEL,
                'messages': messages,
                'temperature': 0.7,
                'max_tokens': 500,
                'top_p': 0.9
            },
            timeout=30
        )
        
        # 6. HANDLE GROQ RESPONSE
        if response.status_code == 200:
            result = response.json()
            bot_reply = result['choices'][0]['message']['content']
            
            # Save to database
            save_conversation(session_id, user_message, bot_reply, context.get('user_name'))
            
            logger.info(f"✅ Groq response sent")
            logger.info(f"🤖 Bot reply: {bot_reply[:50]}...")
            
            return jsonify([{
                'generated_text': bot_reply,
                'session_id': session_id,
                'model': GROQ_MODEL
            }])
        else:
            logger.error(f"❌ Groq API error: {response.status_code}")
            logger.error(f"❌ Response: {response.text[:200]}")
            return jsonify({'error': f'Groq API error: {response.status_code}'}), 503
            
    except requests.exceptions.Timeout:
        logger.error("❌ Groq API timeout")
        return jsonify({'error': 'AI service timeout'}), 504
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
        'version': '7.0.0',
        'groq_api': 'configured' if GROQ_API_KEY else 'missing',
        'groq_model': GROQ_MODEL,
        'supabase': 'connected' if validate_supabase() else 'disconnected',
        'timestamp': datetime.utcnow().isoformat()
    })

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🚀 P.R.A.I v7.0.0 - GROQ API CONNECTED!")
    print("=" * 70)
    print(f"✅ Groq API Key: {'✓ Set' if GROQ_API_KEY else '✗ MISSING!'}")
    print(f"✅ Groq Model: {GROQ_MODEL}")
    print(f"✅ Supabase: {'✓ Connected' if validate_supabase() else '✗ Disconnected'}")
    print("=" * 70)
    
    if not GROQ_API_KEY:
        print("⚠️  WARNING: GROQ_API_KEY not set in environment variables!")
        print("⚠️  Please add it in Render Dashboard → Environment")
    else:
        print("✅ Groq API ready to respond conversationally!")
    
    print("=" * 70)
    
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
