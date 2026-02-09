"""
AI Assistant Pro - Backend Server
Professional Edition with Advanced Features
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import PyPDF2
import io
from datetime import datetime
import logging

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
# CONFIGURATION
# ============================================
CONFIG = {
    'API_KEY': 'PUT_YOUR_GROQ_KEY_HERE',  # Replace with your Groq API key
    'API_URL': 'https://api.groq.com/openai/v1/chat/completions',
    'MODEL': 'llama-3.3-70b-versatile',
    'DEFAULT_TEMPERATURE': 0.7,
    'DEFAULT_MAX_TOKENS': 250,
    'REQUEST_TIMEOUT': 30,
    'MAX_FILE_SIZE_MB': 10,
}

# Personality system prompts
PERSONALITIES = {
    'professional': {
        'name': 'Professional',
        'prompt': 'You are a highly professional AI assistant. Communicate in a formal, business-appropriate manner. Be concise, accurate, and respectful. Focus on providing clear, actionable information.'
    },
    'casual': {
        'name': 'Casual',
        'prompt': 'You are a friendly, casual AI assistant. Be warm, conversational, and approachable. Use a relaxed tone while remaining helpful and informative.'
    },
    'technical': {
        'name': 'Technical Expert',
        'prompt': 'You are a technical expert AI assistant. Provide detailed, precise technical explanations. Use proper terminology, include code examples when relevant, and explain complex concepts clearly.'
    },
    'creative': {
        'name': 'Creative',
        'prompt': 'You are a creative, imaginative AI assistant. Think outside the box, provide innovative solutions, and encourage creative thinking. Be enthusiastic and inspirational.'
    },
    'teacher': {
        'name': 'Teacher',
        'prompt': 'You are a patient, educational AI assistant. Explain concepts clearly with examples and analogies. Break down complex topics into digestible parts. Encourage learning and understanding.'
    }
}

# In-memory storage (use database for production)
conversations = {}
session_metadata = {}

# ============================================
# UTILITY FUNCTIONS
# ============================================

def validate_api_key():
    """Check if API key is configured"""
    if CONFIG['API_KEY'] == 'PUT_YOUR_GROQ_KEY_HERE':
        logger.error('API key not configured!')
        return False
    return True

def get_system_message(personality):
    """Get system message for personality"""
    if personality in PERSONALITIES:
        return {
            'role': 'system',
            'content': PERSONALITIES[personality]['prompt']
        }
    return {
        'role': 'system',
        'content': PERSONALITIES['casual']['prompt']
    }

def log_request(session_id, personality, message_length):
    """Log incoming requests"""
    logger.info(
        f"Request - Session: {session_id[:8]}... | "
        f"Personality: {personality} | "
        f"Message length: {message_length}"
    )

def log_response(session_id, status, response_length=0):
    """Log responses"""
    logger.info(
        f"Response - Session: {session_id[:8]}... | "
        f"Status: {status} | "
        f"Length: {response_length}"
    )

# ============================================
# ROUTES
# ============================================

@app.route('/')
def index():
    """Serve the main application"""
    return send_from_directory('.', 'Chatbot.html')


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'active_sessions': len(conversations),
        'model': CONFIG['MODEL'],
        'api_configured': validate_api_key()
    })


@app.route('/chat', methods=['POST'])
def chat():
    """
    Main chat endpoint
    Handles user messages and returns AI responses
    """
    try:
        # Validate API key
        if not validate_api_key():
            return jsonify({'error': 'API key not configured'}), 500

        # Parse request
        data = request.json
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', 'default')
        personality = data.get('personality', 'casual')
        
        # Validate input
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        if len(user_message) > 10000:
            return jsonify({'error': 'Message too long (max 10,000 characters)'}), 400

        # Log request
        log_request(session_id, personality, len(user_message))

        # Initialize conversation
        if session_id not in conversations:
            conversations[session_id] = []
            session_metadata[session_id] = {
                'created_at': datetime.now().isoformat(),
                'personality': personality,
                'message_count': 0
            }
            # Add system message
            conversations[session_id].append(get_system_message(personality))
        
        # Add user message to history
        conversations[session_id].append({
            'role': 'user',
            'content': user_message
        })
        
        # Update metadata
        session_metadata[session_id]['message_count'] += 1
        session_metadata[session_id]['last_activity'] = datetime.now().isoformat()

        # Prepare API request
        headers = {
            'Authorization': f"Bearer {CONFIG['API_KEY']}",
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': CONFIG['MODEL'],
            'messages': conversations[session_id],
            'temperature': CONFIG['DEFAULT_TEMPERATURE'],
            'max_tokens': CONFIG['DEFAULT_MAX_TOKENS']
        }

        # Call Groq API
        response = requests.post(
            CONFIG['API_URL'],
            headers=headers,
            json=payload,
            timeout=CONFIG['REQUEST_TIMEOUT']
        )

        # Handle response
        if response.status_code == 200:
            result = response.json()
            bot_reply = result['choices'][0]['message']['content']
            
            # Add bot response to history
            conversations[session_id].append({
                'role': 'assistant',
                'content': bot_reply
            })
            
            log_response(session_id, 'success', len(bot_reply))
            return jsonify([{'generated_text': bot_reply}])
        
        else:
            error_msg = f'API Error (Status {response.status_code}): {response.text}'
            logger.error(error_msg)
            log_response(session_id, 'error')
            return jsonify({'error': error_msg}), response.status_code

    except requests.exceptions.Timeout:
        logger.error(f'Request timeout for session {session_id}')
        return jsonify({'error': 'Request timeout - AI took too long to respond'}), 504
    
    except requests.exceptions.RequestException as e:
        logger.error(f'Request error: {str(e)}')
        return jsonify({'error': f'Connection error: {str(e)}'}), 500
    
    except Exception as e:
        logger.error(f'Unexpected error: {str(e)}')
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Handle file uploads
    Supports .txt and .pdf files
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        filename = file.filename.lower()
        
        # Check file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to start
        
        max_size = CONFIG['MAX_FILE_SIZE_MB'] * 1024 * 1024
        if file_size > max_size:
            return jsonify({
                'error': f'File too large (max {CONFIG["MAX_FILE_SIZE_MB"]}MB)'
            }), 400

        # Process text file
        if filename.endswith('.txt'):
            try:
                text = file.read().decode('utf-8')
                logger.info(f'Text file uploaded: {filename} ({len(text)} chars)')
                return jsonify({
                    'text': text,
                    'filename': file.filename,
                    'size': len(text)
                })
            except UnicodeDecodeError:
                return jsonify({'error': 'File encoding not supported (use UTF-8)'}), 400
        
        # Process PDF file
        elif filename.endswith('.pdf'):
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
                text = ''
                for page_num, page in enumerate(pdf_reader.pages):
                    text += page.extract_text() + '\n'
                
                logger.info(f'PDF uploaded: {filename} ({len(pdf_reader.pages)} pages, {len(text)} chars)')
                return jsonify({
                    'text': text,
                    'filename': file.filename,
                    'pages': len(pdf_reader.pages),
                    'size': len(text)
                })
            except Exception as e:
                logger.error(f'PDF processing error: {str(e)}')
                return jsonify({'error': f'PDF processing failed: {str(e)}'}), 500
        
        else:
            return jsonify({
                'error': 'Unsupported file type. Use .txt or .pdf files only.'
            }), 400

    except Exception as e:
        logger.error(f'File upload error: {str(e)}')
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500


@app.route('/clear', methods=['POST'])
def clear_chat():
    """Clear conversation history for a session"""
    try:
        data = request.json if request.json else {}
        session_id = data.get('session_id', 'default')
        
        if session_id in conversations:
            msg_count = len(conversations[session_id])
            conversations[session_id] = []
            
            if session_id in session_metadata:
                session_metadata[session_id]['message_count'] = 0
            
            logger.info(f'Cleared {msg_count} messages for session {session_id}')
        
        return jsonify({
            'status': 'cleared',
            'session_id': session_id
        })
    
    except Exception as e:
        logger.error(f'Clear error: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/sessions', methods=['GET'])
def get_sessions():
    """Get list of active sessions with metadata"""
    try:
        sessions_info = []
        for session_id, metadata in session_metadata.items():
            sessions_info.append({
                'id': session_id,
                'created_at': metadata.get('created_at'),
                'message_count': metadata.get('message_count', 0),
                'personality': metadata.get('personality'),
                'last_activity': metadata.get('last_activity')
            })
        
        return jsonify({
            'sessions': sessions_info,
            'total': len(sessions_info)
        })
    
    except Exception as e:
        logger.error(f'Sessions list error: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get conversation history for a specific session"""
    try:
        if session_id not in conversations:
            return jsonify({'error': 'Session not found'}), 404
        
        return jsonify({
            'session_id': session_id,
            'messages': conversations[session_id],
            'metadata': session_metadata.get(session_id, {})
        })
    
    except Exception as e:
        logger.error(f'Get session error: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/session/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session"""
    try:
        if session_id == 'default':
            return jsonify({'error': 'Cannot delete default session'}), 400
        
        if session_id in conversations:
            del conversations[session_id]
        
        if session_id in session_metadata:
            del session_metadata[session_id]
        
        logger.info(f'Deleted session: {session_id}')
        return jsonify({
            'status': 'deleted',
            'session_id': session_id
        })
    
    except Exception as e:
        logger.error(f'Delete session error: {str(e)}')
        return jsonify({'error': str(e)}), 500


@app.route('/personalities', methods=['GET'])
def get_personalities():
    """Get available personality modes"""
    return jsonify({
        'personalities': {
            key: {
                'name': value['name'],
                'description': value['prompt']
            }
            for key, value in PERSONALITIES.items()
        }
    })


# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f'Internal server error: {str(error)}')
    return jsonify({'error': 'Internal server error'}), 500


# ============================================
# STARTUP
# ============================================

def print_startup_banner():
    """Print startup information"""
    print("\n" + "=" * 70)
    print("🤖 AI ASSISTANT PRO - BACKEND SERVER")
    print("=" * 70)
    print(f"📊 Model: {CONFIG['MODEL']}")
    print(f"🔌 API: Groq")
    print(f"🎭 Personalities: {len(PERSONALITIES)}")
    print(f"✅ API Key: {'Configured' if validate_api_key() else '❌ NOT CONFIGURED'}")
    print("=" * 70)
    print("🚀 Server Status: READY")
    print("🌐 Access: http://127.0.0.1:8000")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    import os
    print_startup_banner()
    
    if not validate_api_key():
        logger.warning("⚠️  WARNING: API key not configured! Update CONFIG['API_KEY']")
    
    # Use environment variable for port (for deployment)
    port = int(os.environ.get('PORT', 8000))
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False  # Disable debug in production
    )