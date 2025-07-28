# app.py
from flask import Flask, request, render_template_string, jsonify, send_from_directory
import os
import requests
import json
import time # For exponential backoff
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- API Keys Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
# Unsplash is no longer needed for this version
# -----------------------------

# Directory for storing generated website files for download
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
WEBSITE_DIR = os.path.join(BASE_DIR, 'websites')
if not os.path.exists(WEBSITE_DIR):
    os.makedirs(WEBSITE_DIR)

# --- Helper function for exponential backoff ---
def api_call_with_backoff(url, headers, payload, max_retries=5, initial_delay=1):
    for i in range(max_retries):
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=300) # Increased timeout for larger generation
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
        /* All CSS from the original file remains the same, as it provides a great UI foundation */
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
        /* MODIFIED FOR TEXTAREA */
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
        /* Fade-in animation */
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
        // Form validation
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

                // Store description and pages for the next step
                sessionStorage.setItem('websiteDescription', description.trim());
                sessionStorage.setItem('websitePages', JSON.stringify(data.pages));
                
                // Redirect to the page management view
                window.location.href = `/manage_pages`;
                
            } catch (error) {
                console.error('Submission error:', error);
                alert('Failed to generate page ideas. ' + error.message);
                
                // Reset UI state
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
        
        # Ensure there are at least a few default pages
        if not pages or len(pages) < 2:
            pages = ["Home", "About", "Contact"]
            
        return jsonify({"pages": pages[:8]}) # Limit to 8 pages max initially
    except Exception as e:
        return jsonify({"error": {"message": f"Failed to call Gemini API: {e}"}}), 500

@app.route('/manage_pages')
def manage_pages():
    # This page will now get its data from sessionStorage on the client-side
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
        /* Reusing the exact same CSS from the original manage_presentation page */
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
                    renderPages(); // Re-render to update numbers
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

@app.route('/generate_website', methods=['POST'])
def generate_website():
    data = request.get_json()
    description, pages = data.get('description'), data.get('pages', [])
    if not description or not pages: 
        return jsonify({"error": "Invalid request data"}), 400

    prompt = f"""
    You are an expert web developer. Your task is to generate a complete, single-file, responsive website based on a user's request.

    **Website Description:** "{description}"
    **Pages to Create:** {', '.join(pages)}

    **INSTRUCTIONS:**
    1.  **Framework:** Use HTML with Tailwind CSS loaded from a CDN. All CSS must be implemented using Tailwind classes directly in the HTML elements. Do not generate a separate `<style>` block unless absolutely necessary for something Tailwind cannot do (like complex animations).
    2.  **Structure:** Create a single `index.html` file. The website should be a "single-page application" where the different "pages" are actually `<section>` elements.
    3.  **Navigation:**
        * Create a responsive navigation bar at the top (`<nav>`). It should have a simple logo or site title on the left.
        * The navigation links on the right must correspond to the requested pages. Each link's `href` should point to the ID of a section (e.g., `<a href="#about">About</a>`).
        * The nav should have a subtle background color (e.g., `bg-slate-800/80`), be fixed to the top, and have a backdrop blur effect.
    4.  **Sections (Pages):**
        * For each page in the list, create a `<section>` tag with a corresponding `id` (e.g., `<section id="about" class="min-h-screen ...">`).
        * Each section should have padding (`p-8` or more) and be designed to fill roughly the height of the screen (`min-h-screen`).
        * Populate each section with relevant, high-quality placeholder content that matches the page's purpose and the overall website description. Use a mix of headings (`h1`, `h2`), paragraphs (`p`), and placeholder images from `https://placehold.co/`. For example, an "About" page should have text about the company's mission, and a "Services" page should have cards describing different services.
    5.  **JavaScript:**
        * Generate a `<script>` block to be placed before the closing `</body>` tag.
        * The script should handle smooth scrolling for the navigation links. When a nav link is clicked, it should smoothly scroll to the corresponding section.
        * Add a small feature: highlight the active navigation link based on which section is currently visible in the viewport.
    6.  **Footer:** Include a simple `<footer>` at the bottom with a copyright notice.
    7.  **Content Quality:** The generated content (headings, paragraphs) should be well-written, professional, and tailored to the website's description.

    **RESPONSE FORMAT:**
    Return a single, raw JSON object with three keys: "html", "css", and "javascript".
    - `html`: The full HTML content, from `<!DOCTYPE html>` to `</html>`.
    - `css`: An empty string, as all styling should be done with Tailwind classes in the HTML.
    - `javascript`: The complete JavaScript code for the `<script>` tag, without the `<script>` tags themselves.

    Example JSON structure:
    {{
        "html": "<!DOCTYPE html>...",
        "css": "",
        "javascript": "document.addEventListener('DOMContentLoaded', () => {{...}});"
    }}

    Ensure the JSON is perfectly formatted and contains no extra text, explanations, or markdown.
    """
    
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.6, "responseMimeType": "application/json"}
    }
    
    try:
        result = api_call_with_backoff(api_url, headers={'Content-Type': 'application/json'}, payload=payload)
        website_data_str = result['candidates'][0]['content']['parts'][0]['text']
        website_data = json.loads(website_data_str)
        return jsonify(website_data)

    except Exception as e:
        print(f"Error during website generation: {e}")
        return jsonify({"error": "Failed to generate website content. The model may have returned an invalid format."}), 500

@app.route('/preview')
def preview():
    return render_template_string('''
        <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Website Preview & Download</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #e2e8f0; display: flex; flex-direction: column; height: 100vh; margin: 0; }
        .top-bar { background-color: #1e293b; flex-shrink: 0; }
        .preview-area { flex-grow: 1; background-color: #0f172a; }
        iframe { border: 2px solid #334155; border-radius: 0.5rem; }
        button { transition: all 0.2s ease-in-out; }
        button:hover { transform: translateY(-2px); box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
    </style>
</head>
<body>
    <div class="top-bar p-4 flex justify-between items-center shadow-lg z-10">
        <div>
            <h1 class="text-2xl font-bold text-white">Website Preview</h1>
            <p class="text-slate-400">Here is the website generated by the AI. You can download the source files below.</p>
        </div>
        <div class="flex items-center gap-4">
            <button id="downloadHtmlBtn" class="bg-blue-600 text-white font-bold py-2 px-4 rounded-lg">Download HTML</button>
            <button id="downloadCssBtn" class="bg-green-600 text-white font-bold py-2 px-4 rounded-lg">Download CSS</button>
            <button id="downloadJsBtn" class="bg-yellow-500 text-black font-bold py-2 px-4 rounded-lg">Download JS</button>
        </div>
    </div>
    <div class="preview-area p-4">
        <iframe id="preview-frame" class="w-full h-full bg-white"></iframe>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const storedData = localStorage.getItem('websiteData');
            if (!storedData) {
                alert("No website data found to preview.");
                return;
            }

            const websiteData = JSON.parse(storedData);
            const { html, css, javascript } = websiteData;

            // Combine files for preview
            const fullHtml = `
                ${html.replace('</head>', `<style>${css}</style></head>`)}
            `.replace('</body>', `<script>${javascript}<\/script></body>`);

            const previewFrame = document.getElementById('preview-frame');
            previewFrame.srcdoc = fullHtml;

            // Setup download buttons
            document.getElementById('downloadHtmlBtn').addEventListener('click', () => downloadFile('index.html', html, 'text/html'));
            document.getElementById('downloadCssBtn').addEventListener('click', () => downloadFile('style.css', css, 'text/css'));
            document.getElementById('downloadJsBtn').addEventListener('click', () => downloadFile('script.js', javascript, 'application/javascript'));
        });

        function downloadFile(filename, content, mimeType) {
            const blob = new Blob([content], { type: mimeType });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }
    </script>
</body>
</html>''')


if __name__ == '__main__':
    app.run(debug=True, port=5001)
