# app.py
from flask import Flask, request, render_template_string, jsonify, send_from_directory
import os
import requests
import json
import time # For exponential backoff
from dotenv import load_dotenv
from PIL import Image # Import the Pillow library for image resizing

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- API Keys Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "YOUR_UNSPLASH_ACCESS_KEY_HERE")
# -----------------------------

# Directory for storing downloaded images
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
IMAGES_DIR = os.path.join(BASE_DIR, 'images')
if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)

# --- Helper function for exponential backoff ---
def api_call_with_backoff(url, headers, payload, max_retries=5, initial_delay=1):
    for i in range(max_retries):
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=300) # Increased timeout
            if not response.ok:
                print(f"--- API Error Response ---")
                print(f"Status Code: {response.status_code}")
                try: print(f"Response JSON: {response.json()}")
                except json.JSONDecodeError: print(f"Response Text: {response.text}")
                print(f"--------------------------")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"API call failed with HTTPError (retry {i+1}/{max_retries}): {e}")
            if i >= max_retries - 1: raise
            time.sleep(initial_delay * (2 ** i))
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            print(f"API call failed with network error (retry {i+1}/{max_retries}): {e}")
            if i >= max_retries - 1: raise
            time.sleep(initial_delay * (2 ** i))

# --- Helper function to download and resize an image ---
def download_image(image_url, filename):
    try:
        response = requests.get(image_url, stream=True)
        response.raise_for_status()
        with Image.open(response.raw) as img:
            img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
            filepath = os.path.join(IMAGES_DIR, filename)
            img.save(filepath, 'JPEG', quality=85, optimize=True)
        return os.path.join('images', filename).replace('\\', '/')
    except Exception as e:
        print(f"Error during image processing: {e}")
        return None

# --- Helper function to search Unsplash ---
def search_unsplash_image(query):
    if not UNSPLASH_ACCESS_KEY or UNSPLASH_ACCESS_KEY == "YOUR_UNSPLASH_ACCESS_KEY_HERE":
        print("Unsplash API key not configured. Using placeholder.")
        return f"https://placehold.co/1280x800/1e293b/e2e8f0?text={query.replace(' ', '+')}"
    
    url = "https://api.unsplash.com/search/photos"
    params = {"query": query, "per_page": 1, "orientation": "landscape"}
    headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
    try:
        res = requests.get(url, headers=headers, params=params)
        res.raise_for_status()
        data = res.json()
        return data['results'][0]['urls']['regular'] if data['results'] else None
    except Exception as e:
        print(f"Error searching Unsplash for query '{query}': {e}")
        return f"https://placehold.co/1280x800/1e293b/e2e8f0?text={query.replace(' ', '+')}"

@app.route('/')
def index():
    return render_template_string('''
        <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Website Generator</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%); color: #e2e8f0; min-height: 100vh; margin: 0; padding: 0; overflow-x: hidden; position: relative; display: flex; align-items: center; justify-content: center; }
        .bg-animation { position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1; will-change: transform; }
        .floating-orb { position: absolute; border-radius: 50%; background: radial-gradient(circle, rgba(99, 179, 237, 0.4) 0%, rgba(139, 92, 246, 0.2) 70%, transparent 100%); animation: float 8s ease-in-out infinite; will-change: transform; backface-visibility: hidden; }
        .floating-orb:nth-child(1) { width: clamp(60px, 8vw, 120px); height: clamp(60px, 8vw, 120px); top: 15%; left: 10%; animation-delay: 0s; }
        .floating-orb:nth-child(2) { width: clamp(40px, 6vw, 80px); height: clamp(40px, 6vw, 80px); top: 60%; right: 15%; animation-delay: 2s; }
        .floating-orb:nth-child(3) { width: clamp(80px, 10vw, 150px); height: clamp(80px, 10vw, 150px); bottom: 15%; left: 20%; animation-delay: 4s; }
        .floating-orb:nth-child(4) { width: clamp(30px, 4vw, 60px); height: clamp(30px, 4vw, 60px); top: 30%; right: 30%; animation-delay: 1s; }
        @keyframes float { 0%, 100% { transform: translateY(0px) translateX(0px) scale(1); opacity: 0.6; } 50% { transform: translateY(-15px) translateX(10px) scale(1.05); opacity: 0.8; } }
        .grid-pattern { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-image: linear-gradient(rgba(99, 179, 237, 0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(99, 179, 237, 0.08) 1px, transparent 1px); background-size: clamp(30px, 5vw, 50px) clamp(30px, 5vw, 50px); animation: gridMove 25s linear infinite; z-index: 1; will-change: transform; }
        @keyframes gridMove { 0% { transform: translate(0, 0); } 100% { transform: translate(50px, 50px); } }
        .container { max-width: min(90vw, 750px); margin: clamp(20px, 5vh, 50px) auto; padding: clamp(1.5rem, 4vw, 3rem); background: rgba(30, 41, 59, 0.95); backdrop-filter: blur(20px); border: 1px solid rgba(99, 179, 237, 0.3); border-radius: clamp(1rem, 2vw, 1.5rem); box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(99, 179, 237, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.1); position: relative; z-index: 10; transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1); display: flex; flex-direction: column; align-items: center; justify-content: center; }
        @media (hover: hover) { .container:hover { transform: translateY(-3px); } }
        textarea { width: 100%; padding: clamp(0.75rem, 3vw, 1rem) clamp(1rem, 4vw, 1.5rem); border-radius: clamp(0.5rem, 2vw, 0.75rem); border: 2px solid rgba(71, 85, 105, 0.4); background: rgba(51, 65, 85, 0.9); backdrop-filter: blur(10px); color: #e2e8f0; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); font-size: clamp(1rem, 3vw, 1.1rem); line-height: 1.5; -webkit-appearance: none; appearance: none; min-height: 120px; resize: vertical; }
        textarea:focus { border-color: #63b3ed; box-shadow: 0 0 0 3px rgba(99, 179, 237, 0.25), 0 8px 25px rgba(99, 179, 237, 0.15); outline: none; transform: translateY(-1px); }
        button { background: linear-gradient(135deg, #63b3ed, #90cdf4); color: #1a202c; padding: clamp(0.75rem, 3vw, 1rem) clamp(1.5rem, 5vw, 2.5rem); border-radius: clamp(0.75rem, 2vw, 1rem); font-weight: 600; cursor: pointer; border: none; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); font-size: clamp(1rem, 3vw, 1.1rem); position: relative; overflow: hidden; box-shadow: 0 8px 25px rgba(99, 179, 237, 0.3); min-height: 48px; display: inline-flex; align-items: center; justify-content: center; white-space: nowrap; }
        #submitBtn { width: 320px !important; max-width: 100%; margin: 0 auto; display: block; font-size: 1.15rem; }
        @media (hover: hover) { button:hover:not(:disabled) { background: linear-gradient(135deg, #90cdf4, #bee3f8); transform: translateY(-2px); box-shadow: 0 12px 35px rgba(99, 179, 237, 0.4); } }
        button:active:not(:disabled) { transform: translateY(0); transition: transform 0.1s; }
        button:disabled { background: linear-gradient(135deg, #4a5568, #2d3748); cursor: not-allowed; color: #a0aec0; transform: none; }
        .loading-spinner { border: 3px solid rgba(99, 179, 237, 0.3); border-top: 3px solid #63b3ed; border-radius: 50%; width: clamp(28px, 5vw, 35px); height: clamp(28px, 5vw, 35px); animation: spin 1s linear infinite; display: none; margin-left: clamp(0.75rem, 3vw, 1.5rem); flex-shrink: 0; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .title-glow { background: linear-gradient(135deg, #63b3ed, #a78bfa, #f093fb); background-size: 200% 200%; -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; animation: gradientShift 4s ease infinite; font-size: clamp(2rem, 8vw, 3rem); line-height: 1.2; margin-bottom: clamp(1rem, 4vw, 1.5rem); }
        @keyframes gradientShift { 0%, 100% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } }
        .form-group { position: relative; margin-bottom: clamp(1.5rem, 4vw, 2rem); }
        .description-text { font-size: clamp(1rem, 3vw, 1.125rem); line-height: 1.6; margin-bottom: clamp(2rem, 5vw, 2.5rem); }
        .label-text { font-size: clamp(1rem, 3vw, 1.125rem); margin-bottom: clamp(0.75rem, 2vw, 1rem); }
        .button-container { display: flex; align-items: center; justify-content: center; flex-wrap: nowrap; gap: clamp(0.75rem, 3vw, 1.5rem); margin-top: clamp(1.5rem, 4vw, 2rem); }
        .fade-in { animation: fadeIn 0.8s cubic-bezier(0.4, 0, 0.2, 1) forwards; opacity: 0; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>
    <div class="bg-animation">
        <div class="grid-pattern"></div>
        <div class="floating-orb"></div><div class="floating-orb"></div><div class="floating-orb"></div><div class="floating-orb"></div>
    </div>

    <div class="container text-center fade-in">
        <h1 class="title-glow font-bold">🌐 AI Website Generator</h1>
        <p class="description-text text-gray-300">Describe the website you want to create, and let AI build a foundation for you.</p>
        
        <form id="descriptionForm" onsubmit="submitDescription(event)" novalidate>
            <div class="text-left">
                <label for="description" class="label-text text-gray-200 block font-semibold">Describe your ideal website:</label>
                <div class="form-group">
                    <textarea 
                        id="description" 
                        name="description" 
                        placeholder="e.g., A modern portfolio for a photographer named Jane Doe, with a gallery, an about page, and a contact form." 
                        required
                        autocomplete="off"
                        spellcheck="true"
                    ></textarea>
                </div>
            </div>
            <div class="button-container">
                <button type="submit" id="submitBtn" aria-describedby="loading-status">
                    Plan Website Pages
                </button>
                <div id="loadingSpinner" class="loading-spinner" role="status" aria-label="Loading"></div>
            </div>
            <div id="loading-status" class="sr-only" aria-live="polite"></div>
        </form>
    </div>

    <script>
        function validateInput(description) {
            if (!description || description.trim().length < 10) {
                return 'Please provide a more detailed description (at least 10 characters).';
            }
            if (description.trim().length > 1000) {
                return 'Description is too long. Please keep it under 1000 characters.';
            }
            return null;
        }

        async function submitDescription(event) {
            event.preventDefault();
            
            const btn = document.getElementById('submitBtn');
            const spinner = document.getElementById('loadingSpinner');
            const description = document.getElementById('description').value;
            const statusElement = document.getElementById('loading-status');
            
            const validationError = validateInput(description);
            if (validationError) {
                alert(validationError);
                return;
            }
            
            btn.disabled = true;
            btn.innerHTML = 'Planning...';
            spinner.style.display = 'inline-block';
            statusElement.textContent = 'Generating website page ideas...';
            
            try {
                const res = await fetch('/suggest_pages', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ description: description.trim() })
                });
                
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.error?.message || `Server error: ${res.status}`);
                }
                
                const data = await res.json();
                
                if (!data.pages || !Array.isArray(data.pages)) {
                    throw new Error('Invalid response format from server.');
                }

                sessionStorage.setItem('websiteDescription', description.trim());
                sessionStorage.setItem('websitePages', JSON.stringify(data.pages));
                
                window.location.href = `/manage_pages`;
                
            } catch (error) {
                console.error('Submission error:', error);
                alert('Failed to generate page ideas. ' + error.message);
                
                btn.disabled = false;
                btn.innerHTML = '✨ Plan Website Pages';
                spinner.style.display = 'none';
                statusElement.textContent = '';
            }
        }
    </script>
</body>
</html>''')

@app.route('/suggest_pages', methods=['POST'])
def suggest_pages():
    data = request.get_json()
    if not (description := data.get('description')): 
        return jsonify({"error": "No description provided"}), 400
    
    prompt = f'For a website described as "{description}", suggest 4 to 6 essential page names. Examples: Home, About Us, Services, Portfolio, Blog, Contact. Return as a simple comma-separated list. Exclude any numbering or extra text.'
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.5}}
    
    try:
        result = api_call_with_backoff(api_url, {'Content-Type': 'application/json'}, payload)
        text_response = result['candidates'][0]['content']['parts'][0]['text']
        pages = [p.strip() for p in text_response.strip().split(',') if p.strip()]
        
        if not pages or len(pages) < 2:
            pages = ["Home", "About", "Contact"]
            
        return jsonify({"pages": pages[:8]})
    except Exception as e:
        return jsonify({"error": {"message": f"Failed to call Gemini API: {e}"}}), 500

@app.route('/manage_pages')
def manage_pages():
    return render_template_string('''
        <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manage Website Pages</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%); color: #e2e8f0; min-height: 100vh; margin: 0; padding: 0; overflow-x: hidden; position: relative; }
        .bg-animation { position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1; will-change: transform; }
        .floating-orb { position: absolute; border-radius: 50%; background: radial-gradient(circle, rgba(99, 179, 237, 0.4) 0%, rgba(139, 92, 246, 0.2) 70%, transparent 100%); animation: float 8s ease-in-out infinite; will-change: transform; backface-visibility: hidden; }
        .floating-orb:nth-child(1) { width: clamp(60px, 8vw, 120px); height: clamp(60px, 8vw, 120px); top: 15%; left: 10%; animation-delay: 0s; }
        .floating-orb:nth-child(2) { width: clamp(40px, 6vw, 80px); height: clamp(40px, 6vw, 80px); top: 60%; right: 15%; animation-delay: 2s; }
        .main-container { max-width: min(90vw, 800px); margin: clamp(20px, 5vh, 50px) auto; padding: clamp(1.5rem, 4vw, 2.5rem); background: rgba(30, 41, 59, 0.95); backdrop-filter: blur(20px); border: 1px solid rgba(99, 179, 237, 0.3); border-radius: clamp(1rem, 2vw, 1.5rem); box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(99, 179, 237, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.1); position: relative; z-index: 10; transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
        .title-glow { background: linear-gradient(135deg, #63b3ed, #a78bfa, #f093fb); background-size: 200% 200%; -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; animation: gradientShift 4s ease infinite; font-size: clamp(1.5rem, 5vw, 2rem); line-height: 1.2; margin-bottom: clamp(1rem, 3vw, 1.5rem); }
        @keyframes gradientShift { 0%, 100% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } }
        .subtitle { font-size: clamp(0.875rem, 2.5vw, 1rem); line-height: 1.6; margin-bottom: clamp(1.5rem, 4vw, 2rem); color: #94a3b8; }
        #pageList li { display: flex; align-items: center; padding: clamp(0.75rem, 3vw, 1rem); margin: clamp(0.5rem, 2vw, 0.75rem) 0; border-radius: clamp(0.5rem, 2vw, 0.75rem); background: rgba(51, 65, 85, 0.8); backdrop-filter: blur(10px); border: 1px solid rgba(71, 85, 105, 0.4); box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2); cursor: grab; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); position: relative; overflow: hidden; }
        #pageList li.opacity-50 { opacity: 0.5; }
        #pageList li input { background: transparent; flex-grow: 1; outline: none; width: 100%; color: #e2e8f0; font-size: clamp(0.875rem, 2.5vw, 1rem); border: none; padding: clamp(0.25rem, 1vw, 0.5rem); }
        #pageList li button { background: linear-gradient(135deg, #ef4444, #dc2626); color: white; font-weight: bold; width: clamp(1.75rem, 4vw, 2rem); height: clamp(1.75rem, 4vw, 2rem); border-radius: 50%; margin-left: clamp(0.75rem, 3vw, 1rem); border: none; cursor: pointer; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); display: flex; align-items: center; justify-content: center; }
        .add-section { display: flex; align-items: center; gap: clamp(0.75rem, 3vw, 1rem); margin-top: clamp(1.5rem, 4vw, 2rem); flex-wrap: wrap; }
        #newPageInput { flex-grow: 1; min-width: 200px; background: rgba(51, 65, 85, 0.9); padding: clamp(0.75rem, 3vw, 1rem); border-radius: clamp(0.5rem, 2vw, 0.75rem); border: 2px solid rgba(71, 85, 105, 0.4); color: #e2e8f0; font-size: clamp(0.875rem, 2.5vw, 1rem); transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); outline: none; }
        .add-button { background: linear-gradient(135deg, #10b981, #059669); color: white; font-weight: 600; padding: clamp(0.75rem, 3vw, 1rem) clamp(1.25rem, 4vw, 1.5rem); border-radius: clamp(0.5rem, 2vw, 0.75rem); border: none; cursor: pointer; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); font-size: clamp(0.875rem, 2.5vw, 1rem); }
        .final-button-section { text-align: center; margin-top: clamp(2rem, 6vw, 3rem); }
        #generateFinalBtn { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white; font-weight: bold; padding: clamp(0.75rem, 3vw, 1rem) clamp(1.5rem, 5vw, 2rem); border-radius: clamp(0.75rem, 2vw, 1rem); border: none; cursor: pointer; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); font-size: clamp(1rem, 3vw, 1.125rem); }
        #loadingSpinner { border: 4px solid rgba(37, 99, 235, 0.3); border-top: 4px solid #2563eb; border-radius: 50%; width: clamp(28px, 5vw, 32px); height: clamp(28px, 5vw, 32px); animation: spin 1s linear infinite; margin: clamp(1rem, 3vw, 1.5rem) auto 0; filter: drop-shadow(0 0 10px rgba(37, 99, 235, 0.5)); }
        @keyframes spin { to { transform: rotate(360deg); } }
        .fade-in { animation: fadeIn 0.8s cubic-bezier(0.4, 0, 0.2, 1) forwards; opacity: 0; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body class="p-4 md:p-8">
    <div class="bg-animation">
        <div class="floating-orb"></div><div class="floating-orb"></div>
    </div>

    <div class="main-container fade-in">
        <h1 class="title-glow font-bold text-center">✏️ Review Your Website Pages</h1>
        <p class="text-center subtitle">Drag to reorder, edit, add, or delete pages. This will define your website's navigation and structure.</p>
        
        <ul id="pageList" class="mb-6 space-y-3"></ul>
        
        <div class="add-section">
            <input type="text" id="newPageInput" placeholder="Add a new page name" autocomplete="off">
            <button onclick="addPage()" class="add-button">Add Page</button>
        </div>
        
        <div class="final-button-section">
            <button id="generateFinalBtn" onclick="generateFinalWebsite()">🚀 Build My Website</button>
            <div id="loadingSpinner" style="display:none;"></div>
        </div>
    </div>

    <script>
        let pages = [];
        let description = '';
        const list = document.getElementById('pageList');

        document.addEventListener('DOMContentLoaded', () => {
            description = sessionStorage.getItem('websiteDescription');
            const storedPages = sessionStorage.getItem('websitePages');
            if (!description || !storedPages) {
                alert("No website data found. Please start over.");
                window.location.href = '/';
                return;
            }
            pages = JSON.parse(storedPages);
            renderPages();
        });
        
        function renderPages() {
            list.innerHTML = pages.map((page, i) => `
                <li class="flex items-center p-3 my-2 rounded-lg bg-slate-700 shadow-md cursor-grab" draggable="true" data-index="${i}">
                    <span class="text-slate-400 mr-4 font-bold">${i + 1}.</span>
                    <input value="${page.replace(/"/g, '&quot;')}" onchange="updatePage(${i}, this.value)" class="bg-transparent flex-grow focus:outline-none w-full">
                    <button onclick="deletePage(${i})" class="bg-red-500 text-white font-bold w-8 h-8 rounded-full ml-4 hover:bg-red-600 transition-colors">X</button>
                </li>`).join('');
            addDragAndDropHandlers();
        }
        
        function updatePage(index, value) { pages[index] = value; }
        function deletePage(index) { pages.splice(index, 1); renderPages(); }
        function addPage() { 
            const input = document.getElementById('newPageInput'); 
            if (input.value.trim()) { pages.push(input.value.trim()); input.value = ''; renderPages(); } 
        }

        function addDragAndDropHandlers() {
            let draggedItem = null;
            list.querySelectorAll('li').forEach(item => {
                item.addEventListener('dragstart', (e) => {
                    draggedItem = e.target;
                    setTimeout(() => e.target.classList.add('opacity-50'), 0);
                });
                item.addEventListener('dragend', (e) => {
                    e.target.classList.remove('opacity-50');
                    const newPages = Array.from(list.querySelectorAll('li')).map(li => li.querySelector('input').value);
                    pages = newPages;
                    renderPages();
                });
                item.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    const afterElement = getDragAfterElement(list, e.clientY);
                    list.insertBefore(draggedItem, afterElement);
                });
            });
        }
        
        function getDragAfterElement(container, y) {
            const draggableElements = [...container.querySelectorAll('li:not(.opacity-50)')];
            return draggableElements.reduce((closest, child) => {
                const box = child.getBoundingClientRect();
                const offset = y - box.top - box.height / 2;
                if (offset < 0 && offset > closest.offset) { return { offset: offset, element: child }; } 
                else { return closest; }
            }, { offset: Number.NEGATIVE_INFINITY }).element;
        }

        async function generateFinalWebsite() {
            const btn = document.getElementById('generateFinalBtn');
            const spinner = document.getElementById('loadingSpinner');
            btn.style.display = 'none';
            spinner.style.display = 'block';
            
            try { 
                const res = await fetch('/generate_website', { 
                    method: 'POST', 
                    headers: {'Content-Type': 'application/json'}, 
                    body: JSON.stringify({ description: description, pages: pages }) 
                }); 
                
                if (!res.ok) {
                    const errorData = await res.json();
                    throw new Error(errorData.error || 'Server error generating website.');
                }
                
                const websiteData = await res.json();
                localStorage.setItem('websiteData', JSON.stringify(websiteData));
                window.location.href = '/preview';

            } catch (err) { 
                alert('Failed to generate website: ' + err.message); 
                btn.style.display = 'block'; 
                spinner.style.display = 'none'; 
            }
        }
    </script>
</body>
</html>''')

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)

@app.route('/generate_website', methods=['POST'])
def generate_website():
    data = request.get_json()
    description, pages = data.get('description'), data.get('pages', [])
    if not description or not pages: 
        return jsonify({"error": "Invalid request data"}), 400

    prompt = f"""
    You are an expert web developer creating a structured JSON representation of a website.

    **Website Description:** "{description}"
    **Pages to Create:** {', '.join(pages)}

    **INSTRUCTIONS:**
    Your output MUST be a single, raw JSON object. This object will be the data model for a web editor.
    
    **JSON Structure:**
    {{
      "globalStyles": {{
        "theme": "dark",
        "fontFamily": "'Inter', sans-serif",
        "backgroundColor": "#0f172a",
        "textColor": "#e2e8f0",
        "primaryColor": "#4f46e5",
        "secondaryColor": "#1e293b",
        "accentColor": "#38bdf8"
      }},
      "pages": [
        // One object for each page in the list: {', '.join(pages)}
      ]
    }}

    **For each page object in the "pages" array, use this structure:**
    {{
      "id": "page-unique-id", // e.g., "page-home", "page-about"
      "name": "Page Name",   // e.g., "Home", "About Us"
      "styles": {{
        "backgroundColor": "var(--secondary-color)",
        "padding": "6rem 2rem"
      }},
      "elements": [
        // Array of element objects for this page
      ]
    }}

    **For each element in the "elements" array, use this structure:**
    {{
      "id": "el-unique-id", // e.g., "el-home-title", "el-about-image"
      "type": "heading" | "text" | "button" | "image",
      "content": "...", // Text for headings, paragraphs, or buttons. For images, this is an Unsplash search query.
      "link": "#", // A URL link, default to "#"
      "styles": {{
        "position": "absolute",
        "top": "10%", "left": "15%", "width": "70%", "height": "20%",
        "color": "var(--text-color)", "backgroundColor": "transparent", "fontSize": "3rem",
        "textAlign": "center", "borderRadius": "0.5rem", "padding": "1rem 2rem", "border": "none"
      }},
      "hoverStyles": {{
          "backgroundColor": "var(--primary-color)", "transform": "scale(1.05)"
      }}
    }}

    **TASK & LAYOUT RULES:**
    1.  Generate the full JSON object following the schema above exactly.
    2.  Create one page object for each page name provided.
    3.  For each page, create at least 2-4 relevant elements (headings, text, images, buttons).
    4.  **Use absolute positioning for ALL elements.** Provide sensible initial `top`, `left`, `width`, and `height` percentages.
    5.  For `image` elements, the `content` field MUST be a concise, descriptive Unsplash search query.
    6.  Use CSS variables like `var(--primary-color)` in element styles.
    7.  For "Home", create a hero section with a large heading, a sub-paragraph, and a call-to-action button.
    8.  For buttons, provide meaningful hoverStyles. For other elements, you can leave hoverStyles empty or with default values.

    Return ONLY the raw, perfectly formatted JSON. Do not include markdown, explanations, or any other text.
    """
    
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"}
    }
    
    try:
        result = api_call_with_backoff(api_url, headers={'Content-Type': 'application/json'}, payload=payload)
        response_text = result['candidates'][0]['content']['parts'][0]['text']
        
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        cleaned_text = cleaned_text.strip()

        try:
            website_data = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            print(f"Initial JSON parsing failed: {e}. Attempting recovery.")
            if "Extra data" in str(e):
                try:
                    decoder = json.JSONDecoder()
                    obj, end = decoder.raw_decode(cleaned_text)
                    website_data = obj
                    print(f"Successfully recovered JSON object, discarding extra data from index {end}.")
                except json.JSONDecodeError as inner_e:
                    print(f"Recovery failed: {inner_e}")
                    raise inner_e
            else:
                raise e

        if 'pages' not in website_data or 'globalStyles' not in website_data:
            raise ValueError("Generated JSON is missing required 'pages' or 'globalStyles' keys.")

        # Process images
        for page in website_data.get('pages', []):
            for element in page.get('elements', []):
                if element.get('type') == 'image':
                    query = element.get('content')
                    if query:
                        print(f"Fetching image for query '{query}'...")
                        image_url = search_unsplash_image(query)
                        if image_url:
                            filename = f"{element['id']}.jpg"
                            local_path = download_image(image_url, filename)
                            element['src'] = local_path # Add 'src' key with the local path
                        else:
                            element['src'] = f"https://placehold.co/600x400/1e293b/e2e8f0?text=Not+Found"


        return jsonify(website_data)

    except Exception as e:
        print(f"Error during website generation: {e}")
        return jsonify({"error": f"Failed to generate website content: {e}"}), 500


@app.route('/preview')
def preview():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Website Editor</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/interactjs/dist/interact.min.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=Poppins:wght@400;700&family=Roboto:wght@400;700&family=Lora:wght@400;700&family=Playfair+Display:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #e2e8f0; }
        .editor-container { display: grid; grid-template-columns: 1fr 350px; height: 100vh; }
        .main-canvas { display: flex; flex-direction: column; background-color: #1e293b; }
        .properties-panel { background-color: #0f172a; padding: 1rem; overflow-y: auto; border-left: 1px solid #334155; }
        .top-toolbar { background-color: #1e293b; padding: 0.5rem 1rem; border-bottom: 1px solid #334155; flex-shrink: 0; }
        .iframe-wrapper { flex-grow: 1; padding: 1rem; }
        #editor-frame { width: 100%; height: 100%; border: none; background-color: white; border-radius: 0.5rem; transition: all 0.3s ease; }
        .panel-section details { margin-bottom: 1rem; }
        .panel-section summary { font-weight: 600; color: #94a3b8; margin-bottom: 0.75rem; border-bottom: 1px solid #334155; padding-bottom: 0.5rem; cursor: pointer; }
        .prop-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.75rem; }
        .prop-label { font-size: 0.875rem; color: #cbd5e1; margin-bottom: 0.25rem; display: block; }
        .prop-input { width: 100%; background-color: #1e293b; border: 1px solid #475569; color: white; border-radius: 0.375rem; padding: 0.5rem; font-size: 0.875rem; }
        .prop-input[type="color"] { padding: 0.125rem; height: 38px; }
        .selected-in-frame { outline: 3px solid #38bdf8 !important; outline-offset: 2px; box-shadow: 0 0 20px rgba(56, 189, 248, 0.5); }
        .page-tab { background-color: #334155; color: #cbd5e1; padding: 0.25rem 0.75rem; border-radius: 0.375rem; cursor: pointer; transition: all 0.2s ease; }
        .page-tab:hover { background-color: #475569; }
        .page-tab.active { background-color: #4f46e5; color: white; font-weight: 600; }
    </style>
</head>
<body>
    <div class="editor-container">
        <!-- Main Canvas & Toolbar -->
        <div class="main-canvas">
            <div class="top-toolbar flex items-center justify-between">
                <div id="page-tabs" class="flex items-center gap-2">
                    <!-- Page tabs will be inserted here -->
                </div>
                <div class="flex items-center gap-3">
                    <button id="addTextBtn" class="bg-blue-600 text-white text-sm font-semibold py-1 px-3 rounded-md hover:bg-blue-700">Add Text</button>
                    <button id="downloadBtn" class="bg-indigo-600 text-white text-sm font-bold py-1 px-3 rounded-lg hover:bg-indigo-700">Download HTML</button>
                </div>
            </div>
            <div class="iframe-wrapper">
                <iframe id="editor-frame"></iframe>
            </div>
        </div>

        <!-- Properties Panel -->
        <div id="properties-panel" class="properties-panel">
            <!-- This will be populated dynamically -->
        </div>
    </div>

    <script>
        let websiteData = {};
        let selectedElement = null;
        let selectedElementId = null;
        let currentPageId = null;

        document.addEventListener('DOMContentLoaded', () => {
            const storedData = localStorage.getItem('websiteData');
            if (storedData) {
                websiteData = JSON.parse(storedData);
                currentPageId = websiteData.pages[0]?.id;
                renderPageTabs();
                renderWebsite();
                renderPropertiesPanel();
            } else {
                alert("No website data found. Please start over.");
            }
            
            document.getElementById('downloadBtn').addEventListener('click', downloadHTML);
            document.getElementById('addTextBtn').addEventListener('click', addElementToPage('text'));
        });

        // --- RENDER FUNCTIONS ---
        function renderPageTabs() {
            const tabsContainer = document.getElementById('page-tabs');
            tabsContainer.innerHTML = websiteData.pages.map(page => `
                <div class="page-tab ${page.id === currentPageId ? 'active' : ''}" onclick="switchPage('${page.id}')">
                    ${page.name}
                </div>
            `).join('');
        }

        function renderWebsite() {
            const frame = document.getElementById('editor-frame');
            const page = websiteData.pages.find(p => p.id === currentPageId);
            if (!page) return;

            const global = websiteData.globalStyles;
            const googleFont = global.fontFamily.split(',')[0].replace(/'/g, "").replace(/\s/g, '+');
            
            let hoverStyles = '';
            page.elements.forEach(el => {
                if (el.hoverStyles && (el.hoverStyles.backgroundColor || el.hoverStyles.transform)) {
                    hoverStyles += `#${el.id}:hover {
                        ${el.hoverStyles.backgroundColor ? `background-color: ${el.hoverStyles.backgroundColor} !important;` : ''}
                        ${el.hoverStyles.transform ? `transform: ${el.hoverStyles.transform};` : ''}
                        transition: all 0.2s ease-in-out;
                    }`;
                }
            });

            let html = `
            <head>
                <link rel="preconnect" href="https://fonts.googleapis.com">
                <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
                <link href="https://fonts.googleapis.com/css2?family=${googleFont}:wght@400;700&display=swap" rel="stylesheet">
                <style>
                    :root {
                        --background-color: ${global.backgroundColor}; --text-color: ${global.textColor};
                        --primary-color: ${global.primaryColor}; --secondary-color: ${global.secondaryColor};
                        --accent-color: ${global.accentColor};
                    }
                    body { font-family: ${global.fontFamily}; background-color: var(--background-color); color: var(--text-color); margin: 0; position: relative; min-height: 100vh;}
                    .editable-element { cursor: pointer; box-sizing: border-box; }
                    ${hoverStyles}
                </style>
            </head>
            <body>`;

            html += `<div id="page-container" style="position: relative; width: 100%; height: 100vh; background-color: ${page.styles.backgroundColor || 'transparent'};">`;
            
            page.elements.forEach(el => {
                let styles = 'position: absolute;';
                for (const [key, value] of Object.entries(el.styles)) {
                    const cssKey = key.replace(/[A-Z]/g, letter => `-${letter.toLowerCase()}`);
                    styles += `${cssKey}: ${value}; `;
                }

                const content = el.content.replace(/</g, "&lt;").replace(/>/g, "&gt;");

                if(el.type === 'image') {
                     html += `<img id="${el.id}" src="${el.src || ''}" class="editable-element" style="${styles}">`;
                } else if(el.type === 'button') {
                     html += `<button id="${el.id}" class="editable-element" style="${styles}">${content}</button>`;
                }
                else {
                    html += `<div id="${el.id}" class="editable-element" style="${styles}">${el.content}</div>`; // Allow HTML for text
                }
            });

            html += `</div>`;

             html += `<script>
                document.addEventListener('click', (e) => {
                    if (e.target.classList.contains('editable-element')) {
                        window.parent.postMessage({ type: 'elementSelected', id: e.target.id }, '*');
                    }
                });
            <\/script></body>`;

            frame.srcdoc = html;
        }
        
        function renderPropertiesPanel() {
            const panel = document.getElementById('properties-panel');
            let content = '';

            if (selectedElement) {
                content += `<h2 class="text-lg font-bold mb-4 text-white">${selectedElement.type.charAt(0).toUpperCase() + selectedElement.type.slice(1)} Properties</h2>`;
                
                // Content & Style
                content += `<details open class="panel-section"><summary>Content & Style</summary><div class="space-y-3 mt-2">`;
                content += createTextControl('Content', 'content', selectedElement.content);
                content += createColorControl('Color', 'styles.color', selectedElement.styles.color);
                content += createColorControl('Background', 'styles.backgroundColor', selectedElement.styles.backgroundColor);
                content += createRangeControl('Font Size', 'styles.fontSize', selectedElement.styles.fontSize, 0.5, 10, 0.1, 'rem');
                content += createRangeControl('Border Radius', 'styles.borderRadius', selectedElement.styles.borderRadius, 0, 5, 0.1, 'rem');
                content += `</div></details>`;
                
                // Layout
                content += `<details open class="panel-section"><summary>Layout</summary><div class="prop-grid mt-2">`;
                content += createRangeControl('X Pos', 'styles.left', selectedElement.styles.left, 0, 100, 1, '%');
                content += createRangeControl('Y Pos', 'styles.top', selectedElement.styles.top, 0, 100, 1, '%');
                content += createRangeControl('Width', 'styles.width', selectedElement.styles.width, 0, 100, 1, '%');
                content += createRangeControl('Height', 'styles.height', selectedElement.styles.height, 0, 100, 1, '%');
                content += `</div></details>`;
                
                // Actions
                content += `<details class="panel-section"><summary>Actions</summary><div class="space-y-3 mt-2">`;
                content += createTextControl('Link URL', 'link', selectedElement.link);
                content += createColorControl('Hover BG Color', 'hoverStyles.backgroundColor', selectedElement.hoverStyles?.backgroundColor);
                content += `</div></details>`;
            }

            // Global styles
            content += `<details class="panel-section"><summary>Global Styles</summary><div class="space-y-3 mt-2">`;
            content += createFontSelect('Font Family', 'globalStyles.fontFamily', websiteData.globalStyles.fontFamily);
            content += createColorControl('Background', 'globalStyles.backgroundColor', websiteData.globalStyles.backgroundColor);
            content += createColorControl('Text', 'globalStyles.textColor', websiteData.globalStyles.textColor);
            content += createColorControl('Primary', 'globalStyles.primaryColor', websiteData.globalStyles.primaryColor);
            content += createColorControl('Secondary', 'globalStyles.secondaryColor', websiteData.globalStyles.secondaryColor);
            content += `</div></details>`;
            
            panel.innerHTML = content;
            addPanelEventListeners();
        }

        // --- PROPERTY CONTROLS HELPERS ---
        function createTextControl(label, key, value) {
            return `<div><label class="prop-label">${label}</label><input type="text" class="prop-input" data-key="${key}" value="${value || ''}"></div>`;
        }
        function createColorControl(label, key, value) {
            return `<div><label class="prop-label">${label}</label><input type="color" class="prop-input" data-key="${key}" value="${value || '#ffffff'}"></div>`;
        }
        function createRangeControl(label, key, value, min, max, step, unit) {
            const numericValue = parseFloat(value) || 0;
            return `<div><label class="prop-label">${label} (${numericValue}${unit})</label><input type="range" class="w-full" data-key="${key}" data-unit="${unit}" min="${min}" max="${max}" step="${step}" value="${numericValue}"></div>`;
        }
        function createFontSelect(label, key, value) {
             const fonts = ["'Inter', sans-serif", "'Poppins', sans-serif", "'Roboto', sans-serif", "'Lora', serif", "'Playfair Display', serif"];
             let options = fonts.map(f => `<option value="${f}" ${f === value ? 'selected' : ''}>${f.split(',')[0].replace(/'/g, '')}</option>`).join('');
             return `<div><label class="prop-label">${label}</label><select class="prop-input" data-key="${key}">${options}</select></div>`;
        }


        // --- EVENT LISTENERS & HANDLERS ---
        function addPanelEventListeners() {
            document.querySelectorAll('#properties-panel .prop-input, #properties-panel input[type="range"], #properties-panel select').forEach(input => {
                input.addEventListener('input', (e) => handlePropertyChange(e));
            });
        }
        
        function handlePropertyChange(e) {
            const keyPath = e.target.dataset.key;
            let value = e.target.value;

            const keys = keyPath.split('.');
            let targetObject = websiteData;
            for(let i=0; i < keys.length - 1; i++) {
                targetObject = targetObject[keys[i]] = targetObject[keys[i]] || {};
            }
            
            if (keyPath.startsWith('globalStyles')) {
                 targetObject = websiteData.globalStyles;
            } else if (selectedElement) {
                 if(keys[0] === 'styles') targetObject = selectedElement.styles;
                 else if(keys[0] === 'hoverStyles') targetObject = selectedElement.hoverStyles = selectedElement.hoverStyles || {};
                 else targetObject = selectedElement;
            } else { return; }

            const finalKey = keys[keys.length - 1];

            if(e.target.type === 'range') {
                const unit = e.target.dataset.unit || 'rem';
                e.target.previousElementSibling.textContent = `${e.target.name} (${value}${unit})`;
                value += unit;
            }
            
            targetObject[finalKey] = value;
            
            saveAndRerender();
        }
        
        window.addEventListener('message', (event) => {
            if (event.data.type === 'elementSelected') {
                selectedElementId = event.data.id;
                const page = websiteData.pages.find(p => p.id === currentPageId);
                selectedElement = page.elements.find(el => el.id === selectedElementId);
                
                const frameDoc = document.getElementById('editor-frame').contentDocument;
                frameDoc.querySelectorAll('.selected-in-frame').forEach(el => el.classList.remove('selected-in-frame'));
                if (selectedElement) {
                    frameDoc.getElementById(selectedElementId)?.classList.add('selected-in-frame');
                }
                
                renderPropertiesPanel();
            }
        });

        interact('#editor-frame').on('load', function (event) {
            const frameDoc = event.target.contentDocument;
            interact('.editable-element', { context: frameDoc })
                .draggable({
                    listeners: {
                        move(event) {
                            const target = event.target;
                            const x = (parseFloat(target.dataset.x) || 0) + event.dx;
                            const y = (parseFloat(target.dataset.y) || 0) + event.dy;
                            target.style.transform = `translate(${x}px, ${y}px)`;
                            target.dataset.x = x;
                            target.dataset.y = y;
                        },
                        end(event) {
                            const target = event.target;
                            const elementData = findElementById(target.id);
                            if (!elementData) return;
                            const parentRect = frameDoc.getElementById('page-container').getBoundingClientRect();
                            const x = (target.offsetLeft + (parseFloat(target.dataset.x) || 0));
                            const y = (target.offsetTop + (parseFloat(target.dataset.y) || 0));
                            elementData.styles.left = `${(x / parentRect.width * 100).toFixed(2)}%`;
                            elementData.styles.top = `${(y / parentRect.height * 100).toFixed(2)}%`;
                            target.style.transform = '';
                            target.dataset.x = 0; target.dataset.y = 0;
                            saveAndRerender();
                        }
                    }
                })
                .resizable({
                    edges: { left: true, right: true, bottom: true, top: true },
                    listeners: {
                        move: function (event) {
                            let { x, y } = event.target.dataset;
                            x = (parseFloat(x) || 0); y = (parseFloat(y) || 0);
                            Object.assign(event.target.style, { width: `${event.rect.width}px`, height: `${event.rect.height}px` });
                        },
                         end(event) {
                            const target = event.target;
                            const elementData = findElementById(target.id);
                            if (!elementData) return;
                            const parentRect = frameDoc.getElementById('page-container').getBoundingClientRect();
                            elementData.styles.width = `${(event.rect.width / parentRect.width * 100).toFixed(2)}%`;
                            elementData.styles.height = `${(event.rect.height / parentRect.height * 100).toFixed(2)}%`;
                            saveAndRerender();
                         }
                    }
                })
        });
        
        function switchPage(pageId) {
            currentPageId = pageId;
            selectedElement = null;
            selectedElementId = null;
            renderPageTabs();
            renderWebsite();
            renderPropertiesPanel();
        }

        function findElementById(id) {
             const page = websiteData.pages.find(p => p.id === currentPageId);
             return page?.elements.find(el => el.id === id);
        }

        function saveAndRerender() {
            localStorage.setItem('websiteData', JSON.stringify(websiteData));
            renderWebsite();
            setTimeout(() => {
                 if (selectedElementId) {
                     const frameDoc = document.getElementById('editor-frame').contentDocument;
                     frameDoc.getElementById(selectedElementId)?.classList.add('selected-in-frame');
                 }
            }, 100);
        }
        
        function addElementToPage(type) {
            return () => {
                const page = websiteData.pages.find(p => p.id === currentPageId);
                if(!page) return;
                
                const newElement = {
                    id: `el-${Date.now()}`, type: type, link: '#',
                    content: type === 'text' ? 'New Text Block' : 'Click Me',
                    styles: {
                         position: "absolute", top: "40%", left: "40%", width: "20%", height: "10%",
                         color: "var(--text-color)", backgroundColor: type === 'button' ? 'var(--primary-color)' : 'transparent',
                         fontSize: '1rem', textAlign: 'center', borderRadius: '0.25rem'
                    },
                    hoverStyles: {}
                };
                page.elements.push(newElement);
                saveAndRerender();
            }
        }
        
        function downloadHTML() {
            const global = websiteData.globalStyles;
            const googleFont = global.fontFamily.split(',')[0].replace(/'/g, "").replace(/\s/g, '+');

            let finalHtml = `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>My Awesome Website</title>
                <link rel="preconnect" href="https://fonts.googleapis.com">
                <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
                <link href="https://fonts.googleapis.com/css2?family=${googleFont}:wght@400;700&display=swap" rel="stylesheet">
                <style>
                :root {
                    --background-color: ${global.backgroundColor}; --text-color: ${global.textColor};
                    --primary-color: ${global.primaryColor}; --secondary-color: ${global.secondaryColor};
                    --accent-color: ${global.accentColor};
                }
                html { scroll-behavior: smooth; }
                body { font-family: ${global.fontFamily}; background-color: var(--background-color); color: var(--text-color); margin: 0;}
                nav { position: fixed; top: 0; left: 0; right: 0; background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); padding: 1rem 2rem; z-index: 1000; display: flex; justify-content: center; gap: 1.5rem; }
                nav a { color: var(--text-color); text-decoration: none; font-weight: 500; transition: color 0.2s ease; }
                nav a:hover { color: var(--accent-color); }
                section { min-height: 100vh; position: relative; }
                </style>
                <style id="hover-styles"></style>
                </head><body>
                <nav>${websiteData.pages.map(p => `<a href="#${p.id}">${p.name}</a>`).join('')}</nav>
            `;
            
            let hoverCss = '';

            websiteData.pages.forEach(page => {
                 finalHtml += `<section id="${page.id}" style="background-color: ${page.styles.backgroundColor || 'transparent'}; padding: ${page.styles.padding || '0'};">`;
                 page.elements.forEach(el => {
                    let styles = '';
                    for (const [key, value] of Object.entries(el.styles)) {
                        const cssKey = key.replace(/[A-Z]/g, letter => `-${letter.toLowerCase()}`);
                        styles += `${cssKey}: ${value}; `;
                    }
                    if (el.hoverStyles && (el.hoverStyles.backgroundColor || el.hoverStyles.transform)) {
                         hoverCss += `#${el.id}:hover {
                            ${el.hoverStyles.backgroundColor ? `background-color: ${el.hoverStyles.backgroundColor} !important;` : ''}
                            ${el.hoverStyles.transform ? `transform: ${el.hoverStyles.transform};` : ''}
                            transition: all 0.2s ease-in-out;
                        }`;
                    }

                    const elementHtml = el.type === 'image' ? `<img id="${el.id}" src="${el.src || ''}" style="${styles}">`
                                      : el.type === 'button' ? `<button id="${el.id}" style="${styles}">${el.content}</button>`
                                      : `<div id="${el.id}" style="${styles}">${el.content}</div>`;
                    
                    finalHtml += el.link && el.link !== '#' ? `<a href="${el.link}" target="_blank">${elementHtml}</a>` : elementHtml;
                 });
                 finalHtml += `</section>`;
            });

            finalHtml = finalHtml.replace('<style id="hover-styles"></style>', `<style>${hoverCss}</style>`);

            finalHtml += `</body></html>`;

            const blob = new Blob([finalHtml], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `website.html`;
            a.click();
            URL.revokeObjectURL(url);
        }

    </script>
</body>
</html>
''')


if __name__ == '__main__':
    app.run(debug=True, port=5001)
