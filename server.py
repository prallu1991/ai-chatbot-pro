"""
P.R.A.I - PRODUCTION SERVER v6.0.0
STATUS: ✅ TRUE CONVERSATIONAL AI | ✅ ALL PROMPTS | ✅ MEMORY | ✅ SAFETY
FEATURES:
- ✅ General conversation & small talk
- ✅ Knowledge & information retrieval  
- ✅ How-to guides & tutorials
- ✅ Coding assistance
- ✅ Calculations & conversions
- ✅ Real-time data (time/date)
- ✅ Writing & text assistance
- ✅ Personal assistant & planning
- ✅ Opinions & recommendations
- ✅ Error handling & edge cases
- ✅ Safety & refusal prompts
- ✅ Advanced AI capabilities
- ✅ Meta & fun prompts
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
# ENHANCED CONVERSATIONAL SYSTEM PROMPT
# ============================================
SYSTEM_PROMPT = """You are P.R.A.I, a state-of-the-art conversational AI assistant. You are friendly, helpful, and capable of handling ANY topic naturally - just like ChatGPT.

YOUR CAPABILITIES:

1. GENERAL CONVERSATION & SMALL TALK
   - Greet users warmly, ask how they're doing
   - Tell jokes, fun facts, be sarcastic when requested
   - Motivate and encourage users
   - Remember and use the user's name naturally

2. KNOWLEDGE & INFORMATION
   - Answer questions about science, history, technology, etc.
   - Explain complex topics in simple terms
   - Provide summaries and comparisons
   - Give opinions and recommendations when asked

3. HOW-TO & TUTORIALS
   - Provide step-by-step guides for cooking, tech, fitness, etc.
   - Give clear, actionable instructions
   - Break down complex processes

4. CODING & TECHNICAL
   - Write, debug, and optimize code in any language
   - Explain programming concepts
   - Generate templates and examples
   - Fix errors and suggest improvements

5. CALCULATIONS & CONVERSIONS
   - Perform mathematical calculations
   - Convert units (currency, measurements, etc.)
   - Calculate percentages, BMI, factorials, etc.

6. REAL-TIME DATA
   - Provide current time and date
   - Time in any major city
   - (Note: For weather, stocks, news - inform user this requires API key)

7. WRITING & TEXT ASSISTANCE
   - Rewrite and improve text
   - Generate emails, letters, proposals
   - Create social media posts
   - Summarize and extract key points
   - Fix grammar and punctuation

8. PERSONAL ASSISTANT & PLANNING
   - Create meal plans, workout routines
   - Plan trips and itineraries
   - Set reminders and schedules
   - Track budgets and expenses

9. OPINIONS & RECOMMENDATIONS
   - Give balanced, informed opinions
   - Compare products, technologies, services
   - Suggest best options based on needs

10. SAFETY & REFUSAL
    - NEVER provide harmful, illegal, or unethical content
    - NEVER help with hacking, bypassing security, or accessing others' data
    - POLITELY refuse inappropriate requests
    - EXPLAIN why you cannot fulfill the request

11. META & FUN
    - Role-play when asked (pirate, teacher, coach, etc.)
    - Explain things in different styles (like I'm 5)
    - Predict future trends
    - Share interesting AI facts

CONVERSATION GUIDELINES:
- Be conversational, natural, and human-like
- Keep responses concise (2-4 sentences unless detail is requested)
- Ask follow-up questions to engage users
- Remember context from previous messages
- Use the user's name naturally when known
- If unsure, ask for clarification
- Never say "as an AI" or "I don't have memory" - you DO have memory!

Current date and time: {current_time}
"""

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
            'timezone': timezone
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
        'dubai': 'Asia/Dubai', 'moscow': 'Europe/Moscow',
        'new delhi': 'Asia/Kolkata', 'bangalore': 'Asia/Kolkata',
        'chennai': 'Asia/Kolkata', 'kolkata': 'Asia/Kolkata'
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
    except:
        return False

def get_user_context(session_id):
    history = get_conversation_history(session_id, limit=50)
    context = {
        'user_name': None,
        'message_count': len(history),
        'topics': []
    }
    for msg in history[-20:]:
        if not context['user_name'] and msg.get('user_message'):
            msg_lower = msg['user_message'].lower()
            if "my name is" in msg_lower:
                name_part = msg_lower.split("my name is")[-1].strip()
                context['user_name'] = name_part.split()[0].capitalize()
            elif "i am" in msg_lower and len(msg_lower.split()) < 10:
                name_part = msg_lower.split("i am")[-1].strip()
                if len(name_part.split()) == 1:
                    context['user_name'] = name_part.capitalize()
    return context

# ============================================
# UNIVERSAL FILE UPLOAD
# ============================================

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
            return jsonify({'error': 'File too large (max 50MB)'}), 400
        
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
# CHAT API - TRUE CONVERSATIONAL AI
# ============================================

@app.route('/chat', methods=['POST'])
def chat():
    """TRUE CONVERSATIONAL AI - Handles ALL prompts naturally!"""
    try:
        if not GROQ_API_KEY:
            return jsonify({'error': 'AI service not configured'}), 503
        
        data = request.get_json()
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', f'session_{datetime.utcnow().timestamp()}')[:50]
        user_name = data.get('user_name')
        file_info = data.get('file_info')
        
        if not user_message and not file_info:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        logger.info(f"💬 Chat request - Session: {session_id[:8]}")
        
        # ============================================
        # REAL-TIME DATA QUERIES
        # ============================================
        if user_message:
            msg_lower = user_message.lower()
            
            # Time queries
            if any(word in msg_lower for word in ['time', 'clock', 'what time', 'current time']):
                for city in ['new york', 'london', 'tokyo', 'sydney', 'paris', 'berlin', 'mumbai', 'beijing', 'new delhi']:
                    if city in msg_lower:
                        time_data = get_time_for_city(city)
                        if time_data:
                            response = f"The current time in {city.title()} is {time_data['time']} on {time_data['date']}."
                            save_conversation(session_id, user_message, response, user_name, file_info)
                            return jsonify([{'generated_text': response, 'type': 'real_time'}])
                time_data = get_current_time()
                if time_data:
                    response = f"It's {time_data['time']} on {time_data['date']} (Eastern Time)."
                    save_conversation(session_id, user_message, response, user_name, file_info)
                    return jsonify([{'generated_text': response, 'type': 'real_time'}])
            
            # Date queries
            if any(word in msg_lower for word in ['date', 'today', 'what day']):
                time_data = get_current_time()
                if time_data:
                    response = f"Today is {time_data['date']}."
                    save_conversation(session_id, user_message, response, user_name, file_info)
                    return jsonify([{'generated_text': response, 'type': 'real_time'}])
        
        # ============================================
        # GET CONVERSATION CONTEXT & MEMORY
        # ============================================
        history = get_conversation_history(session_id, limit=50)
        context = get_user_context(session_id)
        
        if user_name and not context.get('user_name'):
            context['user_name'] = user_name
        
        # ============================================
        # BUILD MESSAGES WITH FULL CONTEXT
        # ============================================
        messages = []
        
        # System prompt with current time and context
        current_time = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        system_prompt = SYSTEM_PROMPT.format(current_time=current_time)
        
        # Add user context to system prompt
        if context.get('user_name'):
            system_prompt += f"\n\nThe user's name is {context['user_name']}. Always address them by name naturally in conversation."
        
        if context.get('message_count', 0) > 0:
            system_prompt += f"\n\nYou have had {context['message_count']} messages in this conversation. Remember what was discussed and maintain continuity."
        
        messages.append({'role': 'system', 'content': system_prompt})
        
        # Add conversation history (last 20 messages for full context)
        for msg in history[-20:]:
            if msg.get('user_message'):
                messages.append({'role': 'user', 'content': msg['user_message'][:1000]})
            if msg.get('bot_reply'):
                messages.append({'role': 'assistant', 'content': msg['bot_reply'][:2000]})
        
        # Add file context if present
        if file_info:
            file_context = f"[User uploaded a file: {file_info.get('filename', 'file')}]"
            if file_info.get('extracted_text'):
                file_context += f"\n\nFile contents:\n{file_info['extracted_text'][:1000]}"
            user_message = f"{file_context}\n\n{user_message}" if user_message else file_context
        
        # Add current message
        if user_message:
            messages.append({'role': 'user', 'content': user_message[:1000]})
        
        # ============================================
        # CALL GROQ API WITH ENHANCED PARAMETERS
        # ============================================
        response = requests.post(
            GROQ_API_URL,
            headers={
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': GROQ_MODEL,
                'messages': messages,
                'temperature': 0.85,  # Slightly creative for natural conversation
                'max_tokens': 800,     # Longer responses for complex queries
                'top_p': 0.95,
                'frequency_penalty': 0.3,  # Reduce repetition
                'presence_penalty': 0.3    # Encourage topic variety
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            bot_reply = result['choices'][0]['message']['content']
            
            # Save to database
            save_conversation(session_id, user_message, bot_reply, context.get('user_name'), file_info)
            
            logger.info(f"✅ Conversational response sent")
            return jsonify([{
                'generated_text': bot_reply,
                'session_id': session_id,
                'type': 'conversational'
            }])
        else:
            logger.error(f"❌ Groq API error: {response.status_code}")
            return jsonify({'error': 'AI service temporarily unavailable'}), 503
            
    except Exception as e:
        logger.error(f"❌ Chat error: {str(e)}")
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
        'version': '6.0.0',
        'timestamp': datetime.utcnow().isoformat(),
        'features': {
            'conversational_ai': True,
            'real_time_data': True,
            'memory': True,
            'auth': 'gmail_only',
            'capabilities': [
                'general_conversation',
                'knowledge_retrieval',
                'how_to_guides',
                'coding_assistance',
                'calculations',
                'writing_assistance',
                'planning',
                'recommendations',
                'safety_refusal',
                'meta_fun'
            ]
        }
    })

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🚀 P.R.A.I v6.0.0 - TRUE CONVERSATIONAL AI")
    print("=" * 70)
    print(f"✅ Capabilities: General, Knowledge, Coding, Writing, Planning, Safety")
    print(f"✅ Memory: Full conversational context")
    print(f"✅ Real-time: Time & Date queries")
    print(f"✅ Auth: Gmail + Email")
    print("=" * 70)
    
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
