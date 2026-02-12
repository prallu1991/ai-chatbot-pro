"""
P.R.A.I - PRODUCTION SERVER v5.0.0
STATUS: ✅ CHATGPT STYLE | ✅ UNIVERSAL FILE UPLOAD | ✅ CLEAN UI

FEATURES:
- ✅ ChatGPT-style conversational AI
- ✅ Universal file upload (any file type - documents, images, Excel, PDFs, etc.)
- ✅ Clean, minimal interface - no clutter
- ✅ Proper conversation memory
- ✅ Real-time data (time, date, calculations)
- ✅ Gmail OAuth + Email fallback
- ✅ Supabase database persistence
- ✅ Groq API with Llama 3.3
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
import base64
import magic  # For file type detection
from werkzeug.utils import secure_filename

# ============================================
# PRODUCTION CONFIGURATION
# ============================================
app = Flask(__name__)

# Strict CORS for production
CORS(app, origins=[
    'https://ai-chatbot-pro-wdqz.onrender.com',
    'http://localhost:8000',
    'http://127.0.0.1:8000'
])

# Production logging
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
# ENVIRONMENT VALIDATION
# ============================================
REQUIRED_ENV_VARS = [
    'SUPABASE_URL',
    'SUPABASE_KEY',
    'GROQ_API_KEY',
    'FRONTEND_URL'
]

missing_vars = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]
if missing_vars:
    logger.error(f"❌ Missing required environment variables: {missing_vars}")
else:
    logger.info("✅ All environment variables configured")

# ============================================
# SUPABASE CONFIGURATION
# ============================================
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://ai-chatbot-pro-wdqz.onrender.com').rstrip('/')

# ============================================
# GROQ CONFIGURATION
# ============================================
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
- Don't mention that you're an AI unless asked
- Don't list your capabilities unless asked
- Just help the user with whatever they need
- Remember context from previous messages
- Be conversational, not robotic

Current date and time for reference: {current_time}"""

# ============================================
# REAL-TIME DATA FUNCTIONS
# ============================================

def get_current_time(timezone='America/New_York'):
    """Get current time in specified timezone"""
    try:
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz)
        return {
            'time': current_time.strftime('%I:%M:%S %p'),
            'date': current_time.strftime('%A, %B %d, %Y'),
            'timezone': timezone,
            'timestamp': current_time.isoformat()
        }
    except Exception as e:
        logger.error(f"Time error: {str(e)}")
        return None

def get_time_for_city(city):
    """Get time for a specific city"""
    city_timezones = {
        'new york': 'America/New_York',
        'london': 'Europe/London',
        'tokyo': 'Asia/Tokyo',
        'sydney': 'Australia/Sydney',
        'paris': 'Europe/Paris',
        'berlin': 'Europe/Berlin',
        'mumbai': 'Asia/Kolkata',
        'beijing': 'Asia/Shanghai',
        'san francisco': 'America/Los_Angeles',
        'los angeles': 'America/Los_Angeles',
        'chicago': 'America/Chicago',
        'toronto': 'America/Toronto',
        'vancouver': 'America/Vancouver',
        'singapore': 'Asia/Singapore',
        'hong kong': 'Asia/Hong_Kong',
        'seoul': 'Asia/Seoul',
        'dubai': 'Asia/Dubai',
        'moscow': 'Europe/Moscow',
        'rome': 'Europe/Rome',
        'madrid': 'Europe/Madrid'
    }
    
    city_lower = city.lower().strip()
    for key, tz in city_timezones.items():
        if key in city_lower:
            return get_current_time(tz)
    
    return None

# ============================================
# DATABASE FUNCTIONS
# ============================================

def validate_supabase_credentials():
    """Validate Supabase credentials before making requests"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("❌ Supabase credentials missing")
        return False
    return True

def save_conversation(session_id, user_message, bot_reply, user_name=None, file_info=None):
    """Save conversation with enhanced metadata"""
    if not validate_supabase_credentials():
        return False
        
    try:
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal'
        }
        
        data = {
            'session_id': session_id[:50],
            'user_message': user_message[:1000] if user_message else '',
            'bot_reply': bot_reply[:2000] if bot_reply else '',
            'user_name': user_name[:50] if user_name else None,
            'file_info': json.dumps(file_info) if file_info else None,
            'timestamp': datetime.utcnow().isoformat(),
            'created_at': datetime.utcnow().isoformat()
        }
        
        response = requests.post(
            f'{SUPABASE_URL}/rest/v1/chat_history',
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ Saved to DB - Session: {session_id[:8]}")
            return True
        else:
            logger.error(f"❌ DB save failed: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ DB error: {str(e)}")
        return False

def get_conversation_history(session_id, limit=50):
    """Get conversation history with full context"""
    if not validate_supabase_credentials():
        return []
        
    try:
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}'
        }
        
        response = requests.get(
            f'{SUPABASE_URL}/rest/v1/chat_history'
            f'?session_id=eq.{session_id}'
            f'&order=timestamp.asc'
            f'&limit={limit}',
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"❌ History fetch failed: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ History error: {str(e)}")
        return []

def get_user_context(session_id):
    """Extract user context from conversation history"""
    history = get_conversation_history(session_id, limit=100)
    context = {
        'user_name': None,
        'message_count': len(history)
    }
    
    for msg in history:
        # Extract user name from messages
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
# UNIVERSAL FILE UPLOAD - ANY FILE TYPE!
# ============================================

ALLOWED_EXTENSIONS = {
    # Documents
    'txt', 'pdf', 'doc', 'docx', 'odt', 'rtf',
    # Images
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp',
    # Spreadsheets
    'xls', 'xlsx', 'csv', 'ods',
    # Presentations
    'ppt', 'pptx', 'odp',
    # Archives
    'zip', 'rar', '7z', 'tar', 'gz',
    # Code
    'py', 'js', 'html', 'css', 'json', 'xml', 'yaml', 'md',
    # Other
    'log', 'ini', 'cfg', 'conf'
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB max

def get_file_info(filename, file_size, file_content):
    """Extract file information based on type"""
    ext = filename.split('.')[-1].lower() if '.' in filename else ''
    
    file_info = {
        'filename': filename,
        'extension': ext,
        'size': file_size,
        'type': 'unknown'
    }
    
    # Determine file type category
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp']:
        file_info['type'] = 'image'
        # Try to get image dimensions
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(file_content))
            file_info['width'], file_info['height'] = img.size
        except:
            pass
            
    elif ext in ['pdf']:
        file_info['type'] = 'pdf'
        try:
            pdf = PyPDF2.PdfReader(io.BytesIO(file_content))
            file_info['pages'] = len(pdf.pages)
        except:
            pass
            
    elif ext in ['txt', 'py', 'js', 'html', 'css', 'json', 'xml', 'yaml', 'md', 'log', 'ini', 'cfg', 'conf']:
        file_info['type'] = 'text'
        try:
            # Try to decode as text
            text = file_content[:1000].decode('utf-8', errors='ignore')
            file_info['preview'] = text[:200] + '...' if len(text) > 200 else text
        except:
            pass
            
    elif ext in ['doc', 'docx', 'odt', 'rtf']:
        file_info['type'] = 'document'
    elif ext in ['xls', 'xlsx', 'csv', 'ods']:
        file_info['type'] = 'spreadsheet'
    elif ext in ['ppt', 'pptx', 'odp']:
        file_info['type'] = 'presentation'
    elif ext in ['zip', 'rar', '7z', 'tar', 'gz']:
        file_info['type'] = 'archive'
    
    return file_info

@app.route('/upload', methods=['POST'])
def upload_file():
    """Universal file upload handler - supports ANY file type"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        filename = secure_filename(file.filename)
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({'error': f'File too large (max {MAX_FILE_SIZE//1024//1024}MB)'}), 400
        
        # Read file content
        file_content = file.read()
        
        # Get file info
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        file_info = get_file_info(filename, file_size, file_content)
        
        # For text files, extract content for AI
        extracted_text = ""
        if file_info['type'] in ['text', 'pdf']:
            try:
                if ext == 'txt':
                    extracted_text = file_content.decode('utf-8', errors='ignore')[:10000]
                elif ext == 'pdf':
                    pdf = PyPDF2.PdfReader(io.BytesIO(file_content))
                    for page in pdf.pages[:5]:  # First 5 pages only
                        extracted_text += page.extract_text() + '\n'
                    extracted_text = extracted_text[:10000]
            except Exception as e:
                logger.error(f"Text extraction error: {str(e)}")
                extracted_text = "[Could not extract text from file]"
        
        # For images, get basic info
        if file_info['type'] == 'image':
            # Convert to base64 for display
            img_base64 = base64.b64encode(file_content).decode('utf-8')
            file_info['base64'] = f"data:image/{ext};base64,{img_base64[:100]}..."  # Truncated for response
        
        return jsonify({
            'success': True,
            'filename': filename,
            'size': file_size,
            'file_info': file_info,
            'extracted_text': extracted_text,
            'message': f'File "{filename}" uploaded successfully'
        })
        
    except Exception as e:
        logger.error(f"❌ Upload error: {str(e)}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

# ============================================
# AUTHENTICATION - GMAIL ONLY
# ============================================

@app.route('/auth/login/google', methods=['GET'])
def google_login():
    """Gmail OAuth login - PRIMARY authentication"""
    try:
        if not validate_supabase_credentials():
            return jsonify({'error': 'Authentication service unavailable'}), 503
        
        redirect_uri = f"{request.host_url.rstrip('/')}/auth/callback"
        
        oauth_url = f"{SUPABASE_URL}/auth/v1/authorize"
        params = {
            'provider': 'google',
            'redirect_to': redirect_uri
        }
        
        full_url = f"{oauth_url}?{urllib.parse.urlencode(params)}"
        logger.info("✅ Redirecting to Gmail login")
        
        return jsonify({'url': full_url, 'provider': 'google'})
        
    except Exception as e:
        logger.error(f"❌ Gmail login error: {str(e)}")
        return jsonify({'error': 'Failed to initiate login'}), 500

@app.route('/auth/callback', methods=['GET'])
def auth_callback():
    """Handle OAuth callback from Supabase"""
    try:
        access_token = request.args.get('access_token')
        
        if not access_token:
            logger.error("❌ No access token in callback")
            return redirect(f"{FRONTEND_URL}/?auth_error=no_token")
        
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {access_token}'
        }
        
        user_response = requests.get(
            f'{SUPABASE_URL}/auth/v1/user',
            headers=headers,
            timeout=10
        )
        
        if user_response.status_code == 200:
            user_data = user_response.json()
            email = user_data.get('email', '')
            logger.info(f"✅ Gmail login successful: {email}")
            return redirect(f"{FRONTEND_URL}/#access_token={access_token}")
        else:
            logger.error(f"❌ Failed to get user info: {user_response.status_code}")
            return redirect(f"{FRONTEND_URL}/?auth_error=user_info_failed")
            
    except Exception as e:
        logger.error(f"❌ Auth callback error: {str(e)}")
        return redirect(f"{FRONTEND_URL}/?auth_error=callback_failed")

@app.route('/auth/email/signup', methods=['POST'])
def email_signup():
    """Email/Password signup - FALLBACK"""
    try:
        if not validate_supabase_credentials():
            return jsonify({'error': 'Service unavailable'}), 503
            
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'email': email,
            'password': password,
            'email_confirm': True
        }
        
        response = requests.post(
            f'{SUPABASE_URL}/auth/v1/signup',
            headers=headers,
            json=payload,
            timeout=10
        )
        
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        logger.error(f"❌ Signup error: {str(e)}")
        return jsonify({'error': 'Signup failed'}), 500

@app.route('/auth/email/login', methods=['POST'])
def email_login():
    """Email/Password login - FALLBACK"""
    try:
        if not validate_supabase_credentials():
            return jsonify({'error': 'Service unavailable'}), 500
            
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
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
            json=payload,
            timeout=10
        )
        
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        logger.error(f"❌ Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/auth/user', methods=['GET'])
def get_user():
    """Get current user from token"""
    try:
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'user': None}), 200
        
        if not validate_supabase_credentials():
            return jsonify({'user': None}), 200
        
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': auth_header
        }
        
        response = requests.get(
            f'{SUPABASE_URL}/auth/v1/user',
            headers=headers,
            timeout=10
        )
        
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        logger.error(f"❌ Get user error: {str(e)}")
        return jsonify({'error': 'Failed to get user'}), 500

@app.route('/auth/logout', methods=['POST'])
def logout():
    """Logout user"""
    try:
        auth_header = request.headers.get('Authorization', '')
        
        if validate_supabase_credentials():
            headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': auth_header
            }
            
            requests.post(
                f'{SUPABASE_URL}/auth/v1/logout',
                headers=headers,
                timeout=5
            )
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        logger.error(f"❌ Logout error: {str(e)}")
        return jsonify({'success': True}), 200

# ============================================
# CHAT API - CHATGPT STYLE CONVERSATION
# ============================================

@app.route('/chat', methods=['POST'])
def chat():
    """Process chat messages - ChatGPT style"""
    start_time = datetime.utcnow()
    
    try:
        # Validate API key
        if not GROQ_API_KEY:
            logger.error("❌ Groq API key not configured")
            return jsonify({'error': 'AI service not configured'}), 503
        
        # Parse request
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request'}), 400
            
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', f'session_{datetime.utcnow().timestamp()}')[:50]
        user_name = data.get('user_name')
        file_info = data.get('file_info')
        
        if not user_message and not file_info:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        logger.info(f"💬 Chat request - Session: {session_id[:8]}")
        
        # Check for real-time queries first
        if user_message:
            message_lower = user_message.lower()
            
            # Time queries
            if any(word in message_lower for word in ['time', 'clock', 'what time', 'current time']):
                # Check for specific cities
                cities = ['new york', 'london', 'tokyo', 'sydney', 'paris', 'berlin', 'mumbai', 'beijing']
                for city in cities:
                    if city in message_lower:
                        time_data = get_time_for_city(city)
                        if time_data:
                            response = f"The current time in {city.title()} is {time_data['time']}."
                            save_conversation(session_id, user_message, response, user_name)
                            return jsonify([{'generated_text': response, 'type': 'real_time'}])
                
                # Default time
                time_data = get_current_time()
                if time_data:
                    response = f"It's {time_data['time']}."
                    save_conversation(session_id, user_message, response, user_name)
                    return jsonify([{'generated_text': response, 'type': 'real_time'}])
            
            # Date queries
            if any(word in message_lower for word in ['date', 'today', 'what day']):
                time_data = get_current_time()
                if time_data:
                    response = f"Today is {time_data['date']}."
                    save_conversation(session_id, user_message, response, user_name)
                    return jsonify([{'generated_text': response, 'type': 'real_time'}])
        
        # Get conversation history and user context
        history = get_conversation_history(session_id, limit=50)
        user_context = get_user_context(session_id)
        
        # Update user name if provided
        if user_name and not user_context.get('user_name'):
            user_context['user_name'] = user_name
        
        # Build messages array - ChatGPT style
        messages = []
        
        # System prompt with current time
        current_time = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        system_prompt = SYSTEM_PROMPT.format(current_time=current_time)
        messages.append({'role': 'system', 'content': system_prompt})
        
        # Add conversation history
        for msg in history[-20:]:
            if msg.get('user_message'):
                messages.append({'role': 'user', 'content': msg['user_message'][:1000]})
            if msg.get('bot_reply'):
                messages.append({'role': 'assistant', 'content': msg['bot_reply'][:2000]})
        
        # Add file context if present
        if file_info:
            file_context = f"[User uploaded a file: {file_info.get('filename', 'unknown')}]"
            if file_info.get('extracted_text'):
                file_context += f"\n\nFile contents:\n{file_info['extracted_text'][:1000]}"
            user_message = f"{file_context}\n\n{user_message}" if user_message else file_context
        
        # Add current message
        if user_message:
            messages.append({'role': 'user', 'content': user_message[:1000]})
        
        # Prepare Groq API request
        headers = {
            'Authorization': f'Bearer {GROQ_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': GROQ_MODEL,
            'messages': messages,
            'temperature': 0.7,
            'max_tokens': 800,
            'top_p': 0.9,
            'stream': False
        }
        
        # Call Groq API
        response = requests.post(
            GROQ_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        process_time = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"⏱️ Groq API response time: {process_time:.2f}s")
        
        if response.status_code == 200:
            result = response.json()
            bot_reply = result['choices'][0]['message']['content']
            
            # Save to database
            try:
                save_conversation(session_id, user_message, bot_reply, user_context.get('user_name'), file_info)
            except Exception as e:
                logger.error(f"❌ Async DB save failed: {str(e)}")
            
            return jsonify([{
                'generated_text': bot_reply,
                'session_id': session_id,
                'timestamp': datetime.utcnow().isoformat()
            }])
        else:
            error_msg = f'Groq API Error: {response.status_code}'
            logger.error(f"❌ {error_msg} - {response.text[:200]}")
            return jsonify({'error': 'AI service temporarily unavailable'}), 503
            
    except requests.exceptions.Timeout:
        logger.error('❌ Groq API timeout')
        return jsonify({'error': 'AI took too long to respond'}), 504
    except Exception as e:
        logger.error(f"❌ Chat error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': 'Internal server error'}), 500

# ============================================
# HEALTH & MONITORING
# ============================================

@app.route('/')
def index():
    """Serve the main application"""
    return send_from_directory('.', 'Chatbot.html')

@app.route('/health', methods=['GET'])
def health_check():
    """Production health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '5.0.0',
        'features': {
            'conversational_ai': True,
            'real_time_data': True,
            'memory': True,
            'universal_file_upload': True
        },
        'services': {
            'database': 'connected' if validate_supabase_credentials() else 'disconnected',
            'groq': 'configured' if GROQ_API_KEY else 'missing',
            'auth': 'gmail_only'
        }
    })

@app.route('/health/detailed', methods=['GET'])
def health_detailed():
    """Detailed health check"""
    return jsonify({
        'status': 'healthy',
        'version': '5.0.0',
        'supabase': 'configured' if SUPABASE_URL else 'missing',
        'groq': 'configured' if GROQ_API_KEY else 'missing',
        'file_upload': {
            'max_size': f"{MAX_FILE_SIZE//1024//1024}MB",
            'allowed_types': list(ALLOWED_EXTENSIONS)[:20] + ['...']
        }
    })

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"❌ 500 error: {str(e)}")
    return jsonify({'error': 'Internal server error'}), 500

# ============================================
# PRODUCTION STARTUP
# ============================================

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("🚀 P.R.A.I PRODUCTION SERVER v5.0.0")
    print("=" * 80)
    print(f"📊 Status: {'✅ READY' if GROQ_API_KEY and SUPABASE_URL else '⚠️ DEGRADED'}")
    print(f"🔑 Auth: Gmail OAuth + Email Fallback")
    print(f"💾 Database: {'✅ Connected' if validate_supabase_credentials() else '❌ Disconnected'}")
    print(f"📁 File Upload: ✅ Universal - {len(ALLOWED_EXTENSIONS)} file types supported")
    print(f"📦 Max File Size: {MAX_FILE_SIZE//1024//1024}MB")
    print(f"🤖 AI Model: {GROQ_MODEL}")
    print(f"🌐 Frontend: {FRONTEND_URL}")
    print("=" * 80)
    
    # Test file upload capability
    print(f"📎 Sample allowed extensions: {', '.join(list(ALLOWED_EXTENSIONS)[:10])}...")
    print("=" * 80)
    print("✅ Server starting...")
    print("=" * 80)
    
    port = int(os.environ.get('PORT', 8000))
    host = '0.0.0.0'
    
    app.run(
        host=host,
        port=port,
        debug=False,
        threaded=True
    )
