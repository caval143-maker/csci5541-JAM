from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import google.generativeai as genai
import os
from datetime import datetime
import csv
from pathlib import Path
from functools import wraps
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# Configure Gemini API
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.0-flash-exp')

# User credentials - username: (password, prompt_limit)
# prompt_limit: 3 for limited users, -1 for unlimited users
USERS = {
    'limited1': ('pass123', 3),
    'limited2': ('pass123', 3),
    'limited3': ('pass123', 3),
    'limited4': ('pass123', 3),
    'limited5': ('pass123', 3),
    'limited6': ('pass123', 3),
    'limited7': ('pass123', 3),
    'unlimited1': ('pass456', -1),
    'unlimited2': ('pass456', -1),
    'unlimited3': ('pass456', -1),
    'unlimited4': ('pass456', -1),
    'unlimited5': ('pass456', -1),
    'unlimited6': ('pass456', -1),
    'unlimited7': ('pass456', -1),
    'unlimited8': ('pass456', -1),
}

BLOCKED_PROMPT = "College students should be encouraged to pursue subjects that interest them rather than the courses that seem most likely to lead to jobs"
# System prompt to guide AI responses
SYSTEM_PROMPT = """You are a helpful study assistant. Your role is to provide general guidance, suggestions, and help students think through their work.

IMPORTANT RULES:
- Keep ALL responses under 100 words - be concise and focused
- Provide suggestions, outlines, and general guidance only
- DO NOT write complete essays, paragraphs, or full answers that students can copy-paste
- Help students develop their own ideas through questions and prompts
- Offer structural advice (e.g., "Consider organizing your essay with: intro, 3 body paragraphs, conclusion")
- Suggest topics to research or think about
- Ask clarifying questions to help students think deeper

If asked to write a complete essay or full answer, politely decline and instead offer to:
1. Help them brainstorm ideas
2. Suggest an outline structure
3. Provide tips on how to approach the topic
4. Ask questions to help them develop their thoughts"""

# Initialize logs directory and CSV file
LOGS_DIR = Path('logs')
LOGS_DIR.mkdir(exist_ok=True)
CSV_FILE = LOGS_DIR / 'interactions.csv'

# Create CSV with headers if it doesn't exist
if not CSV_FILE.exists():
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'username', 'user_type', 'prompt_number', 'user_prompt', 'ai_response'])

def log_interaction(username, user_type, prompt_number, user_prompt, ai_response):
    """Log chat interaction to CSV"""
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(),
            username,
            user_type,
            prompt_number,
            user_prompt,
            ai_response
        ])

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in USERS and USERS[username][0] == password:
            session['username'] = username
            session['prompt_limit'] = USERS[username][1]
            session['prompts_used'] = 0
            return redirect(url_for('chat'))
        else:
            return render_template('login.html', error='Invalid username or password')
    
    return render_template('login.html')

@app.route('/chat')
@login_required
def chat():
    username = session.get('username')
    prompt_limit = session.get('prompt_limit')
    prompts_used = session.get('prompts_used', 0)
    
    # Check if user has exceeded limit
    if prompt_limit != -1 and prompts_used >= prompt_limit:
        return render_template('no_prompts.html', prompts_used=prompts_used)
    
    return render_template('chat.html', 
                         username=username,
                         prompt_limit=prompt_limit,
                         prompts_used=prompts_used)

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'error': 'Empty message'}), 400
    
    # Check if user is trying to paste the essay prompt directly
    if BLOCKED_PROMPT.lower() in user_message.lower():
        return jsonify({
            'error': 'blocked_prompt',
            'message': 'Please don\'t paste the essay prompt directly. Instead, ask me specific questions about how to approach your essay. For example: "How should I structure my argument?" or "What are some points I could consider?"'
        }), 400
    
    username = session.get('username')
    prompt_limit = session.get('prompt_limit')
    prompts_used = session.get('prompts_used', 0)
    
    # Check prompt limit
    if prompt_limit != -1 and prompts_used >= prompt_limit:
        return jsonify({
            'error': 'limit_reached',
            'message': f'You have reached your limit of {prompt_limit} prompts. No more prompts are available.'
        }), 403
    
    try:
        # Generate response from Gemini
        full_prompt = f"{SYSTEM_PROMPT}\n\nStudent question: {user_message}"
        response = model.generate_content(full_prompt)
        ai_response = response.text
        
        # Increment prompt counter
        prompts_used += 1
        session['prompts_used'] = prompts_used
        
        # Log the interaction
        user_type = 'limited' if prompt_limit == 3 else 'unlimited'
        log_interaction(username, user_type, prompts_used, user_message, ai_response)
        
        # Check if this was the last prompt
        prompts_remaining = prompt_limit - prompts_used if prompt_limit != -1 else -1
        
        return jsonify({
            'response': ai_response,
            'prompts_used': prompts_used,
            'prompts_remaining': prompts_remaining
        })
    
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to get AI response: {str(e)}'}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Use environment variable for port (required for Render)
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
