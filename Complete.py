# app.py
from flask import Flask, request, render_template_string, jsonify, session
import os
import requests
import json
import time # For exponential backoff
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
# A secret key is needed for session management in Flask
app.secret_key = os.urandom(24)

# --- API Keys Configuration ---
# It's recommended to load this from an environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
# -----------------------------

# --- Helper function for exponential backoff ---
def api_call_with_backoff(url, headers, payload, max_retries=5, initial_delay=1):
    """
    Makes an API call with exponential backoff for handling transient errors.
    """
    for i in range(max_retries):
        try:
            # Increased timeout for potentially long generations
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=300)
            if not response.ok:
                print(f"--- API Error Response ---")
                print(f"Status Code: {response.status_code}")
                try: print(f"Response JSON: {response.json()}")
                except json.JSONDecodeError: print(f"Response Text: {response.text}")
                print(f"--------------------------")
            response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
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
    """Renders the main page to get the user's website topic."""
    # This HTML is the same as your original, just with updated text for clarity
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
                body { font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #e2e8f0; }
                .container { background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(15px); }
                .title-glow { background: linear-gradient(135deg, #38bdf8, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
                .loading-spinner { border-top-color: #38bdf8; }
                button:disabled { background: #475569; }
            </style>
        </head>
        <body class="flex items-center justify-center min-h-screen p-4">
            <div class="container max-w-2xl w-full p-8 rounded-2xl shadow-2xl border border-slate-700 text-center">
                <h1 class="text-4xl md:text-5xl font-bold title-glow">AI Website Generator</h1>
                <p class="text-slate-300 mt-4 mb-8">Tell me what your website is about, and I'll create a professional design for you.</p>

                <form id="topicForm" onsubmit="submitTopic(event)">
                    <label for="topic" class="sr-only">Website Topic</label>
                    <input type="text" id="topic" name="topic" placeholder="e.g., A personal portfolio for a photographer" required
                           class="w-full p-4 rounded-lg bg-slate-800 border-2 border-slate-600 focus:border-sky-500 focus:ring-sky-500 focus:outline-none transition text-lg">

                    <div class="mt-6 flex justify-center items-center">
                        <button type="submit" id="submitBtn" class="bg-sky-600 hover:bg-sky-700 text-white font-bold py-3 px-8 rounded-lg text-lg transition-transform transform hover:scale-105">
                            Suggest Pages
                        </button>
                        <div id="loadingSpinner" class="loading-spinner ml-4 w-8 h-8 border-4 rounded-full animate-spin" style="display: none;"></div>
                    </div>
                </form>
            </div>

            <script>
                async function submitTopic(event) {
                    event.preventDefault();
                    const btn = document.getElementById('submitBtn');
                    const spinner = document.getElementById('loadingSpinner');
                    const topic = document.getElementById('topic').value;

                    if (topic.trim().length < 5) {
                        alert('Please provide a more detailed topic.');
                        return;
                    }

                    btn.disabled = true;
                    btn.textContent = 'Analyzing...';
                    spinner.style.display = 'block';

                    try {
                        const res = await fetch('/suggest_pages', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ topic: topic.trim() })
                        });

                        if (!res.ok) {
                            const err = await res.json();
                            throw new Error(err.error?.message || `Server error: ${res.status}`);
                        }

                        const data = await res.json();
                        window.location.href = `/manage_pages?topic=${encodeURIComponent(topic)}&pages=${data.pages.map(p => encodeURIComponent(p)).join(',')}`;
                    } catch (error) {
                        console.error('Submission error:', error);
                        alert('Failed to suggest pages. Please check the console and try again. ' + error.message);
                        btn.disabled = false;
                        btn.textContent = 'Suggest Pages';
                        spinner.style.display = 'none';
                    }
                }
            </script>
        </body>
        </html>
    ''')

@app.route('/suggest_pages', methods=['POST'])
def suggest_pages():
    """Suggests website pages based on the user's topic."""
    data = request.get_json()
    main_topic = data.get('topic')
    if not main_topic:
        return jsonify({"error": "No topic provided"}), 400

    prompt = f'For a website about "{main_topic}", suggest 5 essential pages. Common pages include "Home", "About", "Services", "Portfolio", "Blog", "Contact". Return as a simple comma-separated list. Exclude any explanation. Example: Home, About Us, Our Work, Testimonials, Contact'
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.6}}

    try:
        result = api_call_with_backoff(api_url, {'Content-Type': 'application/json'}, payload)
        text_response = result['candidates'][0]['content']['parts'][0]['text']
        pages = [p.strip() for p in text_response.strip().split(',') if p.strip()]
        return jsonify({"pages": pages})
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return jsonify({"error": {"message": f"Failed to call Gemini API: {e}"}}), 500

@app.route('/manage_pages')
def manage_pages():
    """Allows the user to edit, reorder, add, or delete the suggested pages."""
    topic = request.args.get('topic', 'My Website')
    pages = [p for p in request.args.get('pages', '').split(',') if p]
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
                body { font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #e2e8f0; }
                .container { background: rgba(30, 41, 59, 0.85); backdrop-filter: blur(15px); }
                .title-glow { background: linear-gradient(135deg, #38bdf8, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
                li { cursor: grab; }
                li:active { cursor: grabbing; }
                .ghost { opacity: 0.5; background: #475569; }
                #generateFinalBtn:disabled { background: #475569; }
            </style>
        </head>
        <body class="flex items-center justify-center min-h-screen p-4">
            <div class="container max-w-3xl w-full p-8 rounded-2xl shadow-2xl border border-slate-700">
                <h1 class="text-3xl font-bold title-glow text-center">Finalize Your Website Pages</h1>
                <p class="text-slate-300 mt-2 mb-6 text-center">Drag to reorder, edit, add, or delete pages.</p>
                <ul id="pageList" class="space-y-3 mb-6"></ul>

                <div class="flex gap-4 mt-4">
                    <input type="text" id="newPageInput" placeholder="Add a new page (e.g., FAQ)" class="flex-grow p-3 rounded-lg bg-slate-800 border-2 border-slate-600 focus:border-sky-500 focus:ring-sky-500 focus:outline-none">
                    <button onclick="addPage()" class="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-5 rounded-lg transition">Add</button>
                </div>

                <div class="mt-8 text-center">
                    <button id="generateFinalBtn" onclick="generateWebsite()" class="bg-sky-600 hover:bg-sky-700 text-white font-bold py-3 px-8 rounded-lg text-lg transition-transform transform hover:scale-105">
                        ✨ Generate My Website
                    </button>
                    <div id="loadingSpinner" class="mt-4 mx-auto w-8 h-8 border-4 border-slate-600 border-t-sky-500 rounded-full animate-spin" style="display: none;"></div>
                </div>
            </div>

            <script>
                let pages = {{ pages | tojson | safe }};
                const mainTopic = "{{ topic }}";
                const list = document.getElementById('pageList');
                let draggedItem = null;

                function renderPages() {
                    list.innerHTML = '';
                    if (pages.length === 0) {
                        list.innerHTML = `<p class="text-center text-slate-400">No pages yet. Add one below!</p>`;
                    }
                    pages.forEach((page, index) => {
                        list.innerHTML += \`
                            <li class="flex items-center gap-3 p-3 rounded-lg bg-slate-700 shadow-md" draggable="true" data-index="\${index}">
                                <span class="text-slate-400 font-bold">⠿</span>
                                <input value="\${page.replace(/"/g, '&quot;')}" onchange="updatePage(\${index}, this.value)" class="bg-transparent flex-grow focus:outline-none p-1 focus:bg-slate-800 rounded">
                                <button onclick="deletePage(\${index})" class="bg-red-600 text-white font-bold w-7 h-7 rounded-full hover:bg-red-700 transition">X</button>
                            </li>\`;
                    });
                    addDragHandlers();
                }

                function updatePage(index, value) { pages[index] = value; }
                function deletePage(index) { pages.splice(index, 1); renderPages(); }
                function addPage() {
                    const input = document.getElementById('newPageInput');
                    if (input.value.trim()) { pages.push(input.value.trim()); input.value = ''; renderPages(); }
                }

                function addDragHandlers() {
                    list.querySelectorAll('li').forEach(item => {
                        item.addEventListener('dragstart', (e) => {
                            draggedItem = e.target;
                            setTimeout(() => e.target.classList.add('ghost'), 0);
                        });
                        item.addEventListener('dragend', (e) => {
                            e.target.classList.remove('ghost');
                            draggedItem = null;
                            const newPages = Array.from(list.querySelectorAll('li')).map(li => li.querySelector('input').value);
                            pages = newPages;
                            renderPages();
                        });
                        item.addEventListener('dragover', (e) => {
                            e.preventDefault();
                            const afterElement = getDragAfterElement(list, e.clientY);
                            if (afterElement == null) {
                                list.appendChild(draggedItem);
                            } else {
                                list.insertBefore(draggedItem, afterElement);
                            }
                        });
                    });
                }

                function getDragAfterElement(container, y) {
                    const draggableElements = [...container.querySelectorAll('li:not(.ghost)')];
                    return draggableElements.reduce((closest, child) => {
                        const box = child.getBoundingClientRect();
                        const offset = y - box.top - box.height / 2;
                        return (offset < 0 && offset > closest.offset) ? { offset: offset, element: child } : closest;
                    }, { offset: Number.NEGATIVE_INFINITY }).element;
                }

                async function generateWebsite() {
                    if (pages.length === 0) {
                        alert("Please add at least one page to your website.");
                        return;
                    }
                    const btn = document.getElementById('generateFinalBtn');
                    const spinner = document.getElementById('loadingSpinner');
                    btn.disabled = true;
                    btn.textContent = 'Building Website... Please Wait';
                    spinner.style.display = 'block';

                    try {
                        const res = await fetch('/generate_website', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ topic: mainTopic, pages: pages })
                        });
                        if (!res.ok) {
                             const errText = await res.text();
                             throw new Error('Server error generating website: ' + errText);
                        }
                        const result = await res.json();
                        // Store in session storage to pass to the next page
                        sessionStorage.setItem('websiteData', JSON.stringify(result));
                        window.location.href = '/preview_website';
                    } catch (err) {
                        alert('Failed to generate website: ' + err);
                        btn.disabled = false;
                        btn.textContent = '✨ Generate My Website';
                        spinner.style.display = 'none';
                    }
                }
                renderPages();
            </script>
        </body>
        </html>
    ''', topic=topic, pages=pages)

@app.route('/generate_website', methods=['POST'])
def generate_website():
    """Generates the full HTML for the website based on the topic and page list."""
    data = request.get_json()
    main_topic = data.get('topic')
    user_pages = data.get('pages', [])
    if not main_topic or not user_pages:
        return jsonify({"error": "Invalid request parameters"}), 400

    prompt = f"""
    Act as an expert frontend web developer. Your task is to generate a single, complete, and visually stunning HTML file for a website about "{main_topic}".

    **KEY INSTRUCTIONS:**
    1.  **Single File Architecture:** All HTML, CSS, and JavaScript must be contained within one single `.html` file.
        - Use a `<style>` tag in the `<head>` for all CSS.
        - Use a `<script>` tag before the closing `</body>` tag for any JavaScript.
    2.  **Styling with Tailwind CSS:** You MUST use Tailwind CSS for all styling. Include it via the CDN: `<script src="https://cdn.tailwindcss.com"></script>`. Do not use any other CSS frameworks or external stylesheets.
    3.  **Content Sections:** Create a separate `<section>` for each of the following pages: {', '.join(user_pages)}.
        - Each section must have a unique `id` that matches the page name (e.g., `<section id="about-us">`). Convert page names to kebab-case for the id.
        - Populate each section with high-quality, relevant placeholder text (paragraphs, headings, lists) that fits the theme of "{main_topic}". The content should be substantial and well-written.
    4.  **Navigation Bar:**
        - Create a sticky navigation bar at the top of the page.
        - It must contain links that smoothly scroll to the corresponding section on the page. For example, a link for "About Us" should look like `<a href="#about-us">About Us</a>`.
        - Implement a "mobile menu" (hamburger menu) for smaller screens.
    5.  **Visual Polish:**
        - Use a modern and clean design aesthetic. Incorporate good use of whitespace, typography (e.g., from Google Fonts), and a cohesive color palette.
        - Add subtle hover effects and transitions to interactive elements like buttons and links.
        - The overall layout must be fully responsive and look excellent on all screen sizes, from mobile to desktop.
    6.  **Hero Section:** The first section should be a compelling "hero" section that grabs the user's attention, clearly stating the website's purpose related to "{main_topic}".
    7.  **Footer:** Include a simple footer at the bottom with copyright information and social media links.
    8.  **Output Format:** Your entire output must be ONLY the raw HTML code, starting with `<!DOCTYPE html>` and ending with `</html>`. Do NOT include any explanations, comments outside the code, or markdown formatting like ```html.

    Generate the complete HTML file now.
    """
    api_url = f"[https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent?key=](https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent?key=){GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5}
    }

    try:
        result = api_call_with_backoff(api_url, headers={'Content-Type': 'application/json'}, payload=payload)
        # The entire response is expected to be the HTML code
        html_content = result['candidates'][0]['content']['parts'][0]['text']

        # Clean up the response to ensure it's pure HTML
        if html_content.strip().startswith("```html"):
            html_content = html_content.strip()[7:-3].strip()

        return jsonify({"html_code": html_content})

    except Exception as e:
        print(f"Error during final website generation: {e}")
        return jsonify({"error": f"Failed to generate website code: {e}"}), 500


@app.route('/preview_website')
def preview_website():
    """Displays the generated website code and a live preview in an iframe."""
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Website Preview & Code</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
            <style>
                body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #e2e8f0; }
                #code-editor { font-family: 'Courier New', Courier, monospace; background-color: #1e293b; border-color: #334155; }
                iframe { border: 2px solid #334155; }
                .tab-btn.active { background-color: #0ea5e9; color: white; }
                .tab-btn { background-color: #334155; color: #94a3b8; }
                .tab-content { display: none; }
                .tab-content.active { display: block; }
            </style>
        </head>
        <body class="h-screen flex flex-col p-4 gap-4">
            <header class="flex-shrink-0 flex justify-between items-center">
                <h1 class="text-2xl font-bold text-white">Your Generated Website</h1>
                <div>
                    <button id="copyBtn" class="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded-lg transition">Copy Code</button>
                    <a href="/" class="bg-sky-600 hover:bg-sky-700 text-white font-bold py-2 px-4 rounded-lg transition">Start Over</a>
                </div>
            </header>

            <div class="flex-shrink-0">
                <button class="tab-btn py-2 px-4 rounded-t-lg active" data-tab="preview">Preview</button>
                <button class="tab-btn py-2 px-4 rounded-t-lg" data-tab="code">Code</button>
            </div>

            <main class="flex-grow flex flex-col bg-slate-800 rounded-b-lg rounded-r-lg p-4 overflow-hidden">
                <div id="preview" class="tab-content active h-full">
                    <iframe id="preview-frame" class="w-full h-full bg-white rounded-md"></iframe>
                </div>
                <div id="code" class="tab-content h-full">
                     <textarea id="code-editor" class="w-full h-full p-4 rounded-md text-sm" readonly></textarea>
                </div>
            </main>

            <script>
                document.addEventListener('DOMContentLoaded', () => {
                    const data = sessionStorage.getItem('websiteData');
                    if (data) {
                        const { html_code } = JSON.parse(data);
                        document.getElementById('code-editor').value = html_code;

                        const iframe = document.getElementById('preview-frame');
                        iframe.srcdoc = html_code;
                    } else {
                        document.body.innerHTML = '<h1 class="text-center text-2xl mt-10">No website data found. Please <a href="/" class="text-sky-400 underline">start over</a>.</h1>';
                    }

                    const tabs = document.querySelectorAll('.tab-btn');
                    const contents = document.querySelectorAll('.tab-content');
                    tabs.forEach(tab => {
                        tab.addEventListener('click', () => {
                            tabs.forEach(t => t.classList.remove('active'));
                            tab.classList.add('active');
                            contents.forEach(c => c.classList.remove('active'));
                            document.getElementById(tab.dataset.tab).classList.add('active');
                        });
                    });

                    document.getElementById('copyBtn').addEventListener('click', () => {
                        const code = document.getElementById('code-editor').value;
                        navigator.clipboard.writeText(code).then(() => {
                            const btn = document.getElementById('copyBtn');
                            btn.textContent = 'Copied!';
                            setTimeout(() => { btn.textContent = 'Copy Code'; }, 2000);
                        }, () => {
                            alert('Failed to copy code.');
                        });
                    });
                });
            </script>
        </body>
        </html>
    ''')

if __name__ == '__main__':
    # Use port 5001 to avoid conflicts with other common ports
    app.run(debug=True, port=5001)
