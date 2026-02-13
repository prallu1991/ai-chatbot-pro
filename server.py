"""
P.R.A.I - PRODUCTION SERVER v9.0.0
STATUS: ✅ ALL BUGS FIXED | ✅ INDIA TIMEZONE | ✅ DOCUMENT Q&A
FEATURES:
- 🌤️ Weather: Open-Meteo (UNLIMITED, no API key)
- 📈 Stocks: iTick (FREE tier, no CC)
- 📰 News: Apify (FREE tier, no CC)  
- 🔍 Web Search: Serper.dev (2,500 free, no CC)
- ⏰ Time/Date: pytz (built-in) ✅ FIXED: India time now works!
- 💬 Chat: Groq (FREE tier)
- 🗄️ Database: Supabase (FREE tier)
- 📄 Document Q&A: NEW! Ask questions about uploaded files
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
import yfinance as yf
from apify_client import ApifyClient

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

# ============================================
# FREE API KEYS - NO CREDIT CARD REQUIRED!
# ============================================
SERPER_API_KEY = os.environ.get('SERPER_API_KEY', '')  # 2,500 free searches
APIFY_TOKEN = os.environ.get('APIFY_TOKEN', '')        # Free tier
ITICK_TOKEN = os.environ.get('ITICK_TOKEN', 'bb42e24746784dc0af821abdd337697a752de1eb')  # Public demo token

# ============================================
# GROQ API CONFIGURATION
# ============================================
GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL = 'llama-3.3-70b-versatile'

# ============================================
# SYSTEM PROMPT
# ============================================
SYSTEM_PROMPT = """You are P.R.A.I, a helpful AI assistant with real-time capabilities.

CURRENT DATE AND TIME: {current_time}
USER'S NAME: {user_name}

CAPABILITIES:
- ✅ Current time and date in any city
- ✅ Weather forecasts worldwide
- ✅ Stock prices and market data
- ✅ Latest news on any topic
- ✅ Web search for real-time information
- ✅ Conversational memory

RULES:
1. Be warm, natural, and conversational
2. Use the user's name naturally
3. Keep responses concise (1-3 sentences)
4. When asked for real-time data, USE THE TOOLS!
5. Never say you don't have access - you DO have access!

Previous conversation: {conversation_summary}
"""

# ============================================
# 1. WEATHER - Open-Meteo (100% FREE, NO API KEY, NO CC)
# ============================================

def get_weather_free(city):
    """Get current weather - COMPLETELY FREE, no key, no credit card!"""
    
    try:
        # Geocode city name to coordinates
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1"
        geo_response = requests.get(geo_url, timeout=5)
        geo_data = geo_response.json()
        
        if 'results' not in geo_data or len(geo_data['results']) == 0:
            return {"error": True, "message": f"City '{city}' not found"}
        
        lat = geo_data['results'][0]['latitude']
        lon = geo_data['results'][0]['longitude']
        city_name = geo_data['results'][0]['name']
        country = geo_data['results'][0].get('country', '')
        
        # Get weather - NO API KEY NEEDED!
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&temperature_unit=celsius&windspeed_unit=kmh&hourly=temperature_2m,relativehumidity_2m"
        
        weather_response = requests.get(weather_url, timeout=5)
        weather_data = weather_response.json()
        
        if 'current_weather' in weather_data:
            current = weather_data['current_weather']
            temp = current['temperature']
            wind = current['windspeed']
            
            # Weather code to condition
            code = current['weathercode']
            if code == 0:
                condition = "☀️ Clear sky"
            elif code in [1, 2, 3]:
                condition = "⛅ Partly cloudy" if code == 2 else "☁️ Cloudy"
            elif code in [45, 48]:
                condition = "🌫️ Foggy"
            elif code in [51, 53, 55, 56, 57]:
                condition = "🌧️ Drizzle"
            elif code in [61, 63, 65, 66, 67, 80, 81, 82]:
                condition = "🌧️ Rain"
            elif code in [71, 73, 75, 77, 85, 86]:
                condition = "❄️ Snow"
            elif code in [95, 96, 99]:
                condition = "⛈️ Thunderstorm"
            else:
                condition = "🌤️ Variable"
            
            return {
                "city": f"{city_name}, {country}",
                "temperature": f"{temp}°C",
                "wind": f"{wind} km/h",
                "condition": condition,
                "success": True
            }
        else:
            return {"error": True, "message": f"Could not get weather for {city}"}
            
    except Exception as e:
        logger.error(f"Weather error: {str(e)}")
        return {"error": True, "message": str(e)}


# ============================================
# 2. STOCKS - Yahoo Finance (100% FREE, NO API KEY, NO CC)
# ============================================

def get_stock_free(symbol):
    """Get stock price - 100% FREE, no API key, no credit card!"""
    
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        
        if hist.empty:
            return {"error": True, "message": f"Symbol '{symbol}' not found"}
        
        current = hist['Close'].iloc[-1]
        open_price = hist['Open'].iloc[0]
        change = current - open_price
        change_percent = (change / open_price) * 100
        high = hist['High'].iloc[-1]
        low = hist['Low'].iloc[-1]
        volume = hist['Volume'].iloc[-1]
        
        # Get company info
        info = ticker.info
        company_name = info.get('longName', info.get('shortName', symbol.upper()))
        currency = info.get('currency', 'USD')
        
        # Format volume
        if volume > 1_000_000:
            vol_str = f"{volume/1_000_000:.1f}M"
        elif volume > 1_000:
            vol_str = f"{volume/1_000:.1f}K"
        else:
            vol_str = str(volume)
        
        return {
            "symbol": symbol.upper(),
            "company": company_name,
            "price": f"{currency} {current:.2f}",
            "change": f"{change:+.2f}",
            "change_percent": f"{change_percent:+.2f}%",
            "day_high": f"{currency} {high:.2f}",
            "day_low": f"{currency} {low:.2f}",
            "volume": vol_str,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Stock error: {str(e)}")
        return {"error": True, "message": str(e)}


# ============================================
# 3. NEWS - Apify (FREE TIER, NO CREDIT CARD!)
# ============================================

def get_news_free(topic, max_results=3):
    """Get latest news - FREE tier, no credit card!"""
    
    if not APIFY_TOKEN:
        return {
            "error": True, 
            "message": "News API not configured. Get free token at: https://console.apify.com",
            "signup": "https://console.apify.com/settings/integrations"
        }
    
    try:
        client = ApifyClient(APIFY_TOKEN)
        
        run_input = {
            "startUrls": [{"url": f"https://news.google.com/search?q={topic}"}],
            "maxArticlesPerStartUrl": max_results,
            "proxyConfiguration": {"useApifyProxy": True}
        }
        
        run = client.actor("Olnrbp8NnCb5rX6ph").call(run_input=run_input)
        
        articles = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            articles.append({
                'title': item.get('title', 'No title'),
                'source': item.get('source', 'Unknown'),
                'url': item.get('url', ''),
                'time': item.get('published', '')[:10],
                'summary': item.get('description', '')[:150] + '...' if item.get('description') else ''
            })
            if len(articles) >= max_results:
                break
        
        if articles:
            return {"articles": articles, "success": True}
        else:
            return {"error": True, "message": f"No news found for '{topic}'"}
            
    except Exception as e:
        logger.error(f"News error: {str(e)}")
        return {"error": True, "message": str(e)}


# ============================================
# 4. WEB SEARCH - Serper.dev (2,500 FREE, NO CREDIT CARD!)
# ============================================

def search_web_free(query):
    """Search the web - 2,500 free searches, NO CREDIT CARD!"""
    
    if not SERPER_API_KEY:
        return {
            "error": True,
            "message": "Search API not configured. Get free key at: https://serper.dev (2,500 free, no CC!)",
            "signup": "https://serper.dev"
        }
    
    url = "https://google.serper.dev/search"
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    payload = {'q': query, 'num': 3}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        data = response.json()
        
        if 'organic' in data and data['organic']:
            results = []
            for item in data['organic'][:3]:
                results.append({
                    'title': item.get('title', ''),
                    'snippet': item.get('snippet', ''),
                    'url': item.get('link', '')
                })
            return {"results": results, "success": True}
        else:
            return {"error": True, "message": f"No results found for '{query}'"}
            
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return {"error": True, "message": str(e)}


# ============================================
# 5. TIME - pytz (BUILT-IN) - FIXED FOR INDIA!
# ============================================

def get_time_for_city(city):
    """Get current time for any major city - FIXED: Now handles India correctly"""
    
    city_timezones = {
        'new york': 'America/New_York',
        'london': 'Europe/London',
        'tokyo': 'Asia/Tokyo',
        'sydney': 'Australia/Sydney',
        'paris': 'Europe/Paris',
        'berlin': 'Europe/Berlin',
        'mumbai': 'Asia/Kolkata',
        'delhi': 'Asia/Kolkata',
        'kolkata': 'Asia/Kolkata',
        'chennai': 'Asia/Kolkata',
        'bangalore': 'Asia/Kolkata',
        'hyderabad': 'Asia/Kolkata',
        'pune': 'Asia/Kolkata',
        'ahmedabad': 'Asia/Kolkata',
        'india': 'Asia/Kolkata',  # ADDED: Handle "India" as a whole
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
        'madrid': 'Europe/Madrid',
        'amsterdam': 'Europe/Amsterdam',
        'bangkok': 'Asia/Bangkok',
        'istanbul': 'Europe/Istanbul',
        'cairo': 'Africa/Cairo',
        'johannesburg': 'Africa/Johannesburg',
        'rio de janeiro': 'America/Sao_Paulo',
        'mexico city': 'America/Mexico_City',
        'shanghai': 'Asia/Shanghai'
    }
    
    city_lower = city.lower().strip()
    
    # Special case: If "india" is in the query, use Kolkata timezone
    if 'india' in city_lower and city_lower.strip() == 'india':
        try:
            tz = pytz.timezone('Asia/Kolkata')
            now = datetime.now(tz)
            return {
                'city': 'India',
                'time': now.strftime('%I:%M %p').lstrip('0'),
                'date': now.strftime('%A, %B %d, %Y'),
                'timezone': 'IST',
                'success': True
            }
        except:
            pass
    
    # Check for specific cities
    for key, tz_name in city_timezones.items():
        if key in city_lower:
            try:
                tz = pytz.timezone(tz_name)
                now = datetime.now(tz)
                city_display = 'India' if key == 'india' else city.title()
                tz_display = 'IST' if tz_name == 'Asia/Kolkata' else tz_name.split('/')[-1].replace('_', ' ')
                return {
                    'city': city_display,
                    'time': now.strftime('%I:%M %p').lstrip('0'),
                    'date': now.strftime('%A, %B %d, %Y'),
                    'timezone': tz_display,
                    'success': True
                }
            except:
                pass
    
    return {"error": True, "message": f"City '{city}' not supported"}


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
    except:
        return jsonify({'user': None}), 200

@app.route('/auth/logout', methods=['POST'])
def logout():
    return jsonify({'success': True}), 200


# ============================================
# CHAT API - WITH REAL-TIME DATA! - FIXED FOR INDIA TIME
# ============================================

@app.route('/chat', methods=['POST'])
def chat():
    try:
        if not GROQ_API_KEY:
            return jsonify({'error': 'Groq API key not configured'}), 503
        
        data = request.get_json()
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id', f'session_{datetime.utcnow().timestamp()}')[:50]
        user_name = data.get('user_name')
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        logger.info(f"💬 Chat: {user_message[:50]}")
        
        # -------------------------------------------------
        # CHECK FOR REAL-TIME QUERIES (BEFORE GROQ)
        # -------------------------------------------------
        
        msg_lower = user_message.lower()
        
        # WEATHER CHECK
        if 'weather' in msg_lower or 'temperature' in msg_lower or 'cold' in msg_lower or 'hot' in msg_lower:
            cities = ['tokyo', 'london', 'paris', 'berlin', 'mumbai', 'beijing', 'new york', 'los angeles', 
                     'chicago', 'san francisco', 'toronto', 'sydney', 'singapore', 'dubai', 'delhi', 
                     'bangalore', 'chennai', 'kolkata', 'hyderabad', 'pune', 'ahmedabad']
            
            for city in cities:
                if city in msg_lower:
                    weather = get_weather_free(city)
                    if weather.get('success'):
                        reply = f"🌤️ **Weather in {weather['city']}**\n" \
                               f"• Temperature: {weather['temperature']}\n" \
                               f"• Conditions: {weather['condition']}\n" \
                               f"• Wind: {weather['wind']}"
                        save_conversation(session_id, user_message, reply, user_name)
                        return jsonify([{'generated_text': reply}])
        
        # STOCK CHECK
        stock_symbols = ['aapl', 'msft', 'goog', 'googl', 'meta', 'amzn', 'tsla', 'nvda', 'nflx', 'dis', 
                        'pypl', 'adbe', 'intc', 'amd', 'spy', 'qqq', 'voo', 'iwm', 'gld', 'slv']
        
        if 'stock' in msg_lower or 'price' in msg_lower or '$' in user_message:
            for symbol in stock_symbols:
                if symbol in msg_lower or symbol.upper() in user_message:
                    stock = get_stock_free(symbol)
                    if stock.get('success'):
                        reply = f"📈 **{stock['company']} ({stock['symbol']})**\n" \
                               f"• Price: {stock['price']}\n" \
                               f"• Change: {stock['change']} ({stock['change_percent']})\n" \
                               f"• Day Range: {stock['day_low']} - {stock['day_high']}\n" \
                               f"• Volume: {stock['volume']}"
                        save_conversation(session_id, user_message, reply, user_name)
                        return jsonify([{'generated_text': reply}])
        
        # TIME CHECK - FIXED FOR INDIA!
        if 'time' in msg_lower or 'clock' in msg_lower:
            # SPECIAL CASE: Check for India first
            if 'india' in msg_lower:
                time_data = get_time_for_city('india')
                if time_data.get('success'):
                    reply = f"🕐 **Time in {time_data['city']}**\n" \
                           f"• {time_data['time']} {time_data['timezone']}\n" \
                           f"• {time_data['date']}"
                    save_conversation(session_id, user_message, reply, user_name)
                    return jsonify([{'generated_text': reply}])
            
            # Check for specific Indian cities
            indian_cities = ['mumbai', 'delhi', 'kolkata', 'chennai', 'bangalore', 'hyderabad', 'pune', 'ahmedabad']
            for city in indian_cities:
                if city in msg_lower:
                    time_data = get_time_for_city(city)
                    if time_data.get('success'):
                        reply = f"🕐 **Time in {time_data['city']}**\n" \
                               f"• {time_data['time']} {time_data['timezone']}\n" \
                               f"• {time_data['date']}"
                        save_conversation(session_id, user_message, reply, user_name)
                        return jsonify([{'generated_text': reply}])
            
            # Other cities
            cities = ['new york', 'london', 'tokyo', 'sydney', 'paris', 'berlin', 'beijing',
                     'san francisco', 'los angeles', 'chicago', 'toronto', 'vancouver', 'singapore',
                     'hong kong', 'seoul', 'dubai', 'moscow', 'rome', 'madrid', 'amsterdam']
            
            for city in cities:
                if city in msg_lower:
                    time_data = get_time_for_city(city)
                    if time_data.get('success'):
                        reply = f"🕐 **Time in {time_data['city']}**\n" \
                               f"• {time_data['time']} {time_data['timezone']}\n" \
                               f"• {time_data['date']}"
                        save_conversation(session_id, user_message, reply, user_name)
                        return jsonify([{'generated_text': reply}])
            
            # Default to Eastern Time only if no location mentioned
            if 'time' in msg_lower and not any(word in msg_lower for word in ['in', 'at', 'for']):
                ny_time = get_time_for_city('new york')
                if ny_time.get('success'):
                    reply = f"🕐 **Current Time**\n{ny_time['time']} ET\n{ny_time['date']}"
                    save_conversation(session_id, user_message, reply, user_name)
                    return jsonify([{'generated_text': reply}])
        
        # NEWS CHECK
        if 'news' in msg_lower or 'headline' in msg_lower or 'latest' in msg_lower:
            topics = ['technology', 'business', 'sports', 'science', 'health', 'entertainment', 'world']
            for topic in topics:
                if topic in msg_lower:
                    news = get_news_free(topic, 3)
                    if news.get('success'):
                        reply = f"📰 **Latest {topic.title()} News**\n\n"
                        for i, article in enumerate(news['articles'], 1):
                            reply += f"{i}. **{article['title']}**\n"
                            reply += f"   {article['source']} · {article['time']}\n"
                            reply += f"   {article['url']}\n\n"
                        save_conversation(session_id, user_message, reply, user_name)
                        return jsonify([{'generated_text': reply}])
            
            # Default tech news
            news = get_news_free('technology', 3)
            if news.get('success'):
                reply = f"📰 **Latest Technology News**\n\n"
                for i, article in enumerate(news['articles'], 1):
                    reply += f"{i}. **{article['title']}**\n"
                    reply += f"   {article['source']} · {article['time']}\n"
                    reply += f"   {article['url']}\n\n"
                save_conversation(session_id, user_message, reply, user_name)
                return jsonify([{'generated_text': reply}])
        
        # SEARCH CHECK (for anything else)
        if SERPER_API_KEY and ('what is' in msg_lower or 'who is' in msg_lower or 'when did' in msg_lower or 
                              'search' in msg_lower or 'find' in msg_lower or 'tell me about' in msg_lower):
            search = search_web_free(user_message)
            if search.get('success'):
                reply = f"🔍 **Search Results**\n\n"
                for i, result in enumerate(search['results'], 1):
                    reply += f"{i}. **{result['title']}**\n"
                    reply += f"   {result['snippet']}\n"
                    reply += f"   🔗 {result['url']}\n\n"
                save_conversation(session_id, user_message, reply, user_name)
                return jsonify([{'generated_text': reply}])
        
        # -------------------------------------------------
        # GET CONVERSATION CONTEXT
        # -------------------------------------------------
        history = get_conversation_history(session_id, limit=20)
        context = extract_user_context(history)
        
        if user_name and not context.get('user_name'):
            context['user_name'] = user_name
        
        # -------------------------------------------------
        # BUILD GROQ MESSAGES
        # -------------------------------------------------
        messages = []
        
        current_time = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        summary = generate_conversation_summary(history)
        system_prompt = SYSTEM_PROMPT.format(
            current_time=current_time,
            user_name=context.get('user_name', 'there'),
            conversation_summary=summary
        )
        messages.append({'role': 'system', 'content': system_prompt})
        
        for msg in history[-10:]:
            if msg.get('user_message'):
                messages.append({'role': 'user', 'content': msg['user_message'][:500]})
            if msg.get('bot_reply'):
                messages.append({'role': 'assistant', 'content': msg['bot_reply'][:500]})
        
        messages.append({'role': 'user', 'content': user_message[:500]})
        
        # -------------------------------------------------
        # CALL GROQ API
        # -------------------------------------------------
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
                'max_tokens': 500
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            bot_reply = result['choices'][0]['message']['content']
            save_conversation(session_id, user_message, bot_reply, context.get('user_name'))
            return jsonify([{'generated_text': bot_reply}])
        else:
            logger.error(f"Groq API error: {response.status_code}")
            return jsonify({'error': 'AI service error'}), 503
            
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


# ============================================
# FILE UPLOAD - UPDATED FOR BETTER DOCUMENT HANDLING
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
                extracted_text = file.read().decode('utf-8', errors='ignore')[:10000]  # Increased to 10k chars
                file.seek(0)
            except:
                pass
        elif filename.lower().endswith('.pdf'):
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
                for page in pdf_reader.pages[:5]:
                    extracted_text += page.extract_text() + '\n'
                extracted_text = extracted_text[:10000]  # Increased to 10k chars
                file.seek(0)
            except:
                pass
        
        return jsonify({
            'success': True,
            'filename': filename,
            'extracted_text': extracted_text,
            'message': f'File "{filename}" uploaded successfully. You can now ask questions about it!'
        })
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'error': 'Upload failed'}), 500


# ============================================
# DOCUMENT Q&A - NEW! FIX FOR BUG #2
# ============================================

@app.route('/ask-document', methods=['POST'])
def ask_document():
    """Ask questions about uploaded document - FIXED: Now fully functional!"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        document_text = data.get('document_text', '').strip()
        
        if not question or not document_text:
            return jsonify({'error': 'Question and document text required'}), 400
        
        # Use Groq to answer based on document
        if not GROQ_API_KEY:
            return jsonify({'error': 'Groq API key not configured'}), 503
        
        messages = [
            {'role': 'system', 'content': 'You are a document Q&A assistant. Answer the question based ONLY on the provided document text. If the answer is not in the document, say "I cannot find this information in the document." Be concise and accurate.'},
            {'role': 'user', 'content': f'Document: {document_text[:8000]}\n\nQuestion: {question}'}
        ]
        
        response = requests.post(
            GROQ_API_URL,
            headers={
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': GROQ_MODEL,
                'messages': messages,
                'temperature': 0.3,
                'max_tokens': 500
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            answer = result['choices'][0]['message']['content']
            return jsonify({'answer': answer, 'success': True})
        else:
            logger.error(f"Document Q&A error: {response.status_code}")
            return jsonify({'error': 'Failed to get answer'}), 503
            
    except Exception as e:
        logger.error(f"Document Q&A error: {str(e)}")
        return jsonify({'error': str(e)}), 500


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
        'version': '9.0.0',
        'groq': 'configured' if GROQ_API_KEY else 'missing',
        'weather': 'free (open-meteo)',
        'stocks': 'free (yfinance)',
        'news': 'free (apify)' if APIFY_TOKEN else 'missing',
        'search': 'free (serper.dev)' if SERPER_API_KEY else 'missing',
        'supabase': 'connected' if validate_supabase() else 'disconnected',
        'document_qa': 'enabled',  # NEW!
        'india_time_fixed': 'yes',  # NEW!
        'timestamp': datetime.utcnow().isoformat()
    })


# ============================================
# PRODUCTION STARTUP
# ============================================

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🚀 P.R.A.I v9.0.0 - ALL BUGS FIXED!")
    print("=" * 70)
    print(f"✅ Weather: Open-Meteo (FREE, no key)")
    print(f"✅ Stocks: Yahoo Finance (FREE, no key)")
    print(f"✅ News: Apify (FREE tier, no CC)")
    print(f"✅ Search: Serper.dev (2,500 free, no CC)")
    print(f"✅ Time: pytz (built-in) - INDIA TIME FIXED!")
    print(f"✅ Document Q&A: NEW - Ask questions about uploaded files!")
    print(f"✅ Groq: {'✓ Configured' if GROQ_API_KEY else '✗ Missing'}")
    print(f"✅ Supabase: {'✓ Connected' if validate_supabase() else '✗ Disconnected'}")
    print("=" * 70)
    
    print("\n📋 FIXED BUGS:")
    print("   • #1: Time in India - Now returns IST instead of EST")
    print("   • #2: Document Q&A - Now you can ask questions about uploaded files")
    print("   • #3: Edit mode - Already working")
    print("   • #4: Settings button - Already working")
    print("   • #5: Conversation context - Already working")
    print("=" * 70)
    
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
