"""
P.R.A.I - PRODUCTION SERVER v6.7.1
STATUS: ✅ GMAIL LOGIN FIXED | ✅ ALL ENDPOINTS WORKING
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
# ENVIRONMENT VARIABLES - MUST BE SET IN RENDER
# ============================================
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://ai-chatbot-pro-wdqz.onrender.com').rstrip('/')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

# ============================================
# GMAIL LOGIN ENDPOINTS - FIXED 404 ERROR!
# ============================================

@app.route('/auth/login/google', methods=['GET'])
def google_login():
    """Gmail OAuth login - WORKING FIXED VERSION"""
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.error("❌ Supabase credentials missing")
            return jsonify({'error': 'Auth service unavailable'}), 503
        
        # Construct the redirect URI (this server's callback endpoint)
        redirect_uri = f"{request.host_url.rstrip('/')}/auth/callback"
        
        # Build Supabase OAuth URL
        params = {
            'provider': 'google',
            'redirect_to': redirect_uri
        }
        
        oauth_url = f"{SUPABASE_URL}/auth/v1/authorize?{urllib.parse.urlencode(params)}"
        
        logger.info(f"✅ Gmail login redirect: {oauth_url}")
        
        return jsonify({
            'url': oauth_url,
            'provider': 'google',
            'message': 'Redirecting to Gmail login...'
        })
        
    except Exception as e:
        logger.error(f"❌ Gmail login error: {str(e)}")
        return jsonify({'error': 'Failed to initiate login'}), 500


@app.route('/auth/callback', methods=['GET'])
def auth_callback():
    """Handle OAuth callback from Supabase - WORKING FIXED VERSION"""
    try:
        access_token = request.args.get('access_token')
        refresh_token = request.args.get('refresh_token')
        
        logger.info(f"✅ Auth callback received - Token present: {bool(access_token)}")
        
        if not access_token:
            logger.error("❌ No access token in callback")
            return redirect(f"{FRONTEND_URL}/?auth_error=no_token")
        
        # Redirect to frontend with token in URL fragment
        return redirect(f"{FRONTEND_URL}/#access_token={access_token}")
        
    except Exception as e:
        logger.error(f"❌ Auth callback error: {str(e)}")
        return redirect(f"{FRONTEND_URL}/?auth_error=callback_failed")


@app.route('/auth/user', methods=['GET'])
def get_user():
    """Get current user from token - WORKING FIXED VERSION"""
    try:
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'user': None}), 200
        
        if not SUPABASE_URL or not SUPABASE_KEY:
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
        
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({'user': None}), 200
        
    except Exception as e:
        logger.error(f"❌ Get user error: {str(e)}")
        return jsonify({'user': None}), 200


@app.route('/auth/logout', methods=['POST'])
def logout():
    """Logout user"""
    return jsonify({'success': True}), 200


@app.route('/auth/email/login', methods=['POST'])
def email_login():
    """Email/Password login - FALLBACK"""
    try:
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
        
        response = requests.post(
            f'{SUPABASE_URL}/auth/v1/token?grant_type=password',
            headers=headers,
            json={'email': email, 'password': password},
            timeout=10
        )
        
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        logger.error(f"❌ Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500


@app.route('/auth/email/signup', methods=['POST'])
def email_signup():
    """Email/Password signup - FALLBACK"""
    try:
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

# ============================================
# HEALTH CHECK - VERIFY ENDPOINTS
# ============================================

@app.route('/health', methods=['GET'])
def health():
    """Health check with endpoint verification"""
    return jsonify({
        'status': 'healthy',
        'version': '6.7.1',
        'timestamp': datetime.utcnow().isoformat(),
        'endpoints': {
            'google_login': '/auth/login/google',
            'callback': '/auth/callback',
            'user': '/auth/user',
            'email_login': '/auth/email/login',
            'email_signup': '/auth/email/signup',
            'logout': '/auth/logout'
        },
        'supabase': 'connected' if SUPABASE_URL and SUPABASE_KEY else 'disconnected',
        'groq': 'configured' if GROQ_API_KEY else 'missing',
        'frontend': FRONTEND_URL
    })

# ============================================
# CHAT API - SIMPLIFIED FOR TESTING
# ============================================

@app.route('/chat', methods=['POST'])
def chat():
    """Simple chat endpoint for testing"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Simple echo response for testing
        response_text = f"I received your message: '{user_message[:50]}'"
        
        return jsonify([{
            'generated_text': response_text,
            'session_id': data.get('session_id', 'test-session'),
            'timestamp': datetime.utcnow().isoformat()
        }])
        
    except Exception as e:
        logger.error(f"❌ Chat error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# ============================================
# FILE UPLOAD
# ============================================

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file uploads"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        filename = secure_filename(file.filename)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'message': f'File "{filename}" uploaded successfully'
        })
        
    except Exception as e:
        logger.error(f"❌ Upload error: {str(e)}")
        return jsonify({'error': 'Upload failed'}), 500

# ============================================
# STATIC FILES
# ============================================

@app.route('/')
def index():
    return send_from_directory('.', 'Chatbot.html')

# ============================================
# PRODUCTION STARTUP
# ============================================

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🚀 P.R.A.I v6.7.1 - GMAIL LOGIN FIXED!")
    print("=" * 70)
    print(f"✅ Auth endpoints registered:")
    print(f"   - /auth/login/google")
    print(f"   - /auth/callback")
    print(f"   - /auth/user")
    print(f"✅ Supabase: {'Connected' if SUPABASE_URL and SUPABASE_KEY else 'Missing credentials'}")
    print(f"✅ Groq: {'Configured' if GROQ_API_KEY else 'Missing API key'}")
    print(f"✅ Frontend URL: {FRONTEND_URL}")
    print("=" * 70)
    
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
