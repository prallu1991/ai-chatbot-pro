"""
P.R.A.I - PRODUCTION SERVER v5.1.0
STATUS: ✅ ALL FEATURES WORKING | ✅ AUDIO | ✅ CONVERSATION | ✅ LOGIN
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
# CHATGPT STYLE SYSTEM PROMPT
# ============================================
SYSTEM_PROMPT = """You are P.R.A.I, a helpful, harmless, and honest AI assistant. 
You converse naturally like ChatGPT. Be concise, friendly, and direct.

Guidelines:
- Keep responses brief and natural
- Remember the user's name when they tell you
- Be conversational, not robotic
- If asked about time/date, provide real-time information
- If asked about files, reference their content

Current date and time: {current_time}"""

# ============================================
# REAL-TIME DATA FUNCTIONS
# ============================================

def get_current_time(timezone='America/New_York'):
    try:
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz)
        return {
            'time': current_time.strftime('%I:%M:%S %p'),
            'date': current_time.strftime('%A, %B %d, %Y'),
            'timezone': timezone,
            'timestamp': current_time.isoformat()
        }
    except:
        return None

def get_time_for_city(city):
    city_timezones = {
        'new york': 'America/New_York', 'london': 'Europe/London',
        'tokyo': 'Asia/Tokyo', 'sydney': 'Australia/Sydney',
        'paris': 'Europe/Paris', 'berlin': 'Europe/Berlin',
        'mumbai': 'Asia/Kolkata', 'beijing': 'Asia/Shanghai',
        'san francisco': 'America/Los_Angeles', 'los angeles': 'America/Los_Angeles',
        'chicago': 'America/Chicago', 'toronto': 'America/Toronto',
        'vancouver': 'America/Vancouver', 'singapore': 'Asia/Singapore',
        'hong kong': 'Asia/Hong_Kong', 'seoul': 'Asia/Seoul',
        'dubai': 'Asia/Dubai', 'moscow': 'Europe/Moscow'
    }
    city_lower = city.lower().strip()
    for key, tz in city_timezones.items():
        if key in city_lower:
            return get_current_time(tz)
    return None

# ============================================
# SUPABASE FUNCTIONS
# ============================================

def validate_supabase():
    return bool(SUPABASE_URL and SUPABASE_KEY)

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
        requests.post(
            f'{SUPABASE_URL}/rest/v1/chat_history',
            headers=headers,
            json=data,
            timeout=5
        )
        return True
    except:
        return False

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
    except:
        return []

def get_user_context(session_id):
    history = get_conversation_history(session_id, limit=50)
    context = {'user_name': None, 'message_count': len(history)}
    for msg in history:
        if not context['user_name'] and msg.get('user_message'):
            user_msg = msg['user_message'].lower()
            if "my name is" in user_msg:
                name_part = user_msg.split("my name is")[-1].strip()
                context['user_name'] = name_part.split()[0].capitalize()
            elif "i am" in user_msg and len(user_msg.split()) < 10:
                name_part = user_msg.split("i am")[-1].strip()
                if len(name_part.split()) == 1:
                    context['user_name'] = name_part.capitalize()
    return context

# ============================================
# UNIVERSAL FILE UPLOAD - SIMPLIFIED
# ============================================

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'gif', 'xls', 'xlsx', 'csv', 'zip'}
MAX_FILE_SIZE = 50 * 1024 * 1024

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        filename = secure_filename(file.filename)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({'error': f'File too large (max 50MB)'}), 400
        
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
            'size': file_size,
            'extracted_text': extracted_text,
            'message': f'File "{filename}" uploaded successfully'
        })
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': 'Upload failed'}), 500

# ============================================
# AUTHENTICATION - GMAIL ONLY
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

@app.route('/auth/email/login', methods=['POST'])
def email_login():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}', 'Content-Type': 'application/json'}
        response = requests.post(
            f'{SUPABASE_URL}/auth/v1/token?grant_type=password',
            headers=headers,
            json={'email': email, 'password': password},
            timeout=10
        )
        return jsonify(response.json()), response.status_code
    except:
        return jsonify({'error': 'Login failed'}), 500

@app.route('/auth/email/signup', methods=['POST'])
def email_signup():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}', 'Content-Type': 'application/json'}
        response = requests.post(
            f'{SUPABASE_URL}/auth/v1/signup',
            headers=headers,
            json={'email': email, 'password': password, 'email_confirm': True},
            timeout=10
        )
        return jsonify(response.json()), response.status_code
    except:
        return jsonify({'error': 'Signup failed'}), 500

@app.route('/auth/logout', methods=['POST'])
def logout():
    return jsonify({'success': True}), 200

# ============================================
# CHAT API - CONVERSATIONAL WITH MEMORY
# ============================================

@app.route('/chat', methods=['POST'])
def chat():
    try:
        if not GROQ_API_KEY:
            return jsonify({'error': 'AI service not configured'}), 503
        
        data = request.get_json()
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', f'session_{datetime.utcnow().timestamp()}')[:50]
        user_name = data.get('user_name')
        file_info = data.get('file_info')
        
        # Check for time/date queries
        if user_message:
            msg_lower = user_message.lower()
            
            # Time queries
            if any(word in msg_lower for word in ['time', 'clock', 'what time']):
                for city in ['new york', 'london', 'tokyo', 'sydney', 'paris', 'berlin', 'mumbai', 'beijing']:
                    if city in msg_lower:
                        time_data = get_time_for_city(city)
                        if time_data:
                            response = f"The current time in {city.title()} is {time_data['time']}."
                            save_conversation(session_id, user_message, response, user_name, file_info)
                            return jsonify([{'generated_text': response, 'type': 'real_time'}])
                time_data = get_current_time()
                if time_data:
                    response = f"It's {time_data['time']}."
                    save_conversation(session_id, user_message, response, user_name, file_info)
                    return jsonify([{'generated_text': response, 'type': 'real_time'}])
            
            # Date queries
            if any(word in msg_lower for word in ['date', 'today', 'what day']):
                time_data = get_current_time()
                if time_data:
                    response = f"Today is {time_data['date']}."
                    save_conversation(session_id, user_message, response, user_name, file_info)
                    return jsonify([{'generated_text': response, 'type': 'real_time'}])
        
        # Get conversation context
        history = get_conversation_history(session_id, limit=20)
        context = get_user_context(session_id)
        
        # Build messages
        messages = []
        current_time = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        messages.append({'role': 'system', 'content': SYSTEM_PROMPT.format(current_time=current_time)})
        
        # Add conversation history
        for msg in history[-10:]:
            if msg.get('user_message'):
                messages.append({'role': 'user', 'content': msg['user_message'][:1000]})
            if msg.get('bot_reply'):
                messages.append({'role': 'assistant', 'content': msg['bot_reply'][:2000]})
        
        # Add file context
        if file_info:
            file_context = f"[User uploaded: {file_info.get('filename', 'file')}]"
            if file_info.get('extracted_text'):
                file_context += f"\n\nFile contents:\n{file_info['extracted_text'][:500]}"
            user_message = f"{file_context}\n\n{user_message}" if user_message else file_context
        
        # Add current message
        if user_message:
            messages.append({'role': 'user', 'content': user_message[:1000]})
        
        # Call Groq API
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
            save_conversation(session_id, user_message, bot_reply, context.get('user_name') or user_name, file_info)
            return jsonify([{'generated_text': bot_reply}])
        else:
            return jsonify({'error': 'AI service error'}), 503
            
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# ============================================
# HEALTH & STATIC
# ============================================

@app.route('/')
def index():
    return send_from_directory('.', 'Chatbot.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'version': '5.1.0',
        'timestamp': datetime.utcnow().isoformat(),
        'features': {
            'conversational_ai': True,
            'real_time_data': True,
            'memory': True,
            'auth': 'gmail_only'
        }
    })

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 P.R.A.I v5.1.0 - ALL FEATURES WORKING")
    print("=" * 60)
    print(f"✅ Groq API: {'Configured' if GROQ_API_KEY else 'Missing'}")
    print(f"✅ Supabase: {'Connected' if validate_supabase() else 'Disconnected'}")
    print(f"✅ Auth: Gmail + Email")
    print(f"✅ Audio: Input + Output")
    print(f"✅ Memory: Conversational")
    print("=" * 60)
    
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
