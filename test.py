# app.py
from flask import Flask, request, render_template_string, jsonify
import os
import requests
import json
import time

# --- Configuration ---
# It's recommended to set the API key as an environment variable
# for security. Create a file named .env and add:
# GEMINI_API_KEY="your_actual_api_key_here"
from dotenv import load_dotenv
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = Flask(__name__)


# --- Helper function for API calls with Exponential Backoff ---
def api_call_with_backoff(url, headers, payload, max_retries=5, initial_delay=1):
    """
    Makes a POST request to an API with exponential backoff for retries.
    This helps handle rate limiting and temporary server issues.
    """
    for i in range(max_retries):
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=300)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"API call failed with HTTPError (retry {i+1}/{max_retries}): {e}")
            if e.response.status_code == 400:
                print(f"Bad request (400), not retrying. Response: {e.response.text}")
                raise
            if i >= max_retries - 1:
                raise
            time.sleep(initial_delay * (2 ** i))
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            print(f"API call failed with network error (retry {i+1}/{max_retries}): {e}")
            if i >= max_retries - 1:
                raise
            time.sleep(initial_delay * (2 ** i))


@app.route('/')
def index():
    """Renders the main page with the input form."""
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
                body {
                    font-family: 'Inter', sans-serif;
                    background-color: #0f172a; /* Slate 900 */
                }
                .title-glow {
                    text-shadow: 0 0 15px rgba(59, 130, 246, 0.5), 0 0 30px rgba(59, 130, 246, 0.3);
                }
            </style>
        </head>
        <body class="flex items-center justify-center min-h-screen bg-slate-900 text-white p-4">
            <div class="w-full max-w-2xl text-center">
                <h1 class="text-4xl md:text-5xl font-bold title-glow mb-4">AI Website Generator</h1>
                <p class="text-slate-400 md:text-lg mb-8">Describe the topic for a professional, single-page website, and AI will build it for you.</p>
                <form id="websiteForm" class="bg-slate-800 p-8 rounded-xl shadow-2xl border border-slate-700">
                    <textarea id="description" class="w-full bg-slate-900 border-2 border-slate-700 rounded-lg p-4 mb-6 text-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-300" rows="4" placeholder="e.g., A modern website for a new coffee shop called 'The Grind' that roasts its own beans."></textarea>
                    <button type="submit" id="submitBtn" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-8 rounded-lg transition-all duration-300 text-lg w-full flex items-center justify-center disabled:bg-slate-500">
                        <svg id="spinner" class="animate-spin -ml-1 mr-3 h-5 w-5 text-white hidden" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span id="button-text">Generate Website</span>
                    </button>
                </form>
            </div>
            <script>
                document.getElementById('websiteForm').addEventListener('submit', async function(e) {
                    e.preventDefault();
                    const description = document.getElementById('description').value;
                    if (description.trim().length < 15) {
                        alert('Please provide a more detailed description (at least 15 characters).');
                        return;
                    }

                    const submitBtn = document.getElementById('submitBtn');
                    const buttonText = document.getElementById('button-text');
                    const spinner = document.getElementById('spinner');

                    submitBtn.disabled = true;
                    buttonText.innerText = 'Generating... Please Wait';
                    spinner.classList.remove('hidden');

                    try {
                        const response = await fetch('/generate_website_json', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ description })
                        });

                        if (!response.ok) {
                            const errorData = await response.json();
                            throw new Error(errorData.error || 'An unknown error occurred.');
                        }

                        const result = await response.json();
                        sessionStorage.setItem('websiteData', JSON.stringify(result));
                        window.location.href = '/preview';

                    } catch (error) {
                        alert('Error generating website: ' + error.message);
                        submitBtn.disabled = false;
                        buttonText.innerText = 'Generate Website';
                        spinner.classList.add('hidden');
                    }
                });
            </script>
        </body>
        </html>
    ''')


@app.route('/generate_website_json', methods=['POST'])
def generate_website_json():
    """
    Receives the website description, calls the Gemini API to generate
    a JSON structure of the website, inspired by a world-class template.
    """
    data = request.get_json()
    description = data.get('description')

    if not description:
        return jsonify({"error": "No description provided"}), 400
    if not GEMINI_API_KEY:
        return jsonify({"error": "API key is not configured on the server."}), 500

    prompt = f"""
    You are an expert web designer creating a JSON structure for a **world-class, single-page website**.
    Your design MUST emulate a modern, responsive portfolio with a dark theme, glowing animated elements, and professional layouts.
    Generate rich, relevant content based on the user's request. **Your primary goal is to ensure the output is a perfectly valid JSON object.**
    
    **USER'S WEBSITE REQUEST:** "{description}"

    **CRITICAL JSON STRUCTURE & DESIGN RULES:**
    1.  **ROOT OBJECT:** The root must be a JSON object with two keys: "globalStyles" and "structure".
    2.  **`globalStyles` OBJECT:**
        -   Create a `fontFamily` property with the string value "'Inter', sans-serif".
        -   Create a `backgroundColor` property with the string value "#030712".
        -   Create a `textColor` property with the string value "#e5e7eb".
        -   Create a `primaryColor` property with the string value "#4f46e5".
        -   Create an `accentColor` property with the string value "#ec4899".
        -   Create a `special` object with one property inside: `bgGrid` with the string value "true".
    3.  **`structure` ARRAY:** This will be an array of objects. Each object represents a section of the website. Create 3 to 4 relevant sections.
    4.  **NAVIGATION SECTION (`type: 'nav'`):**
        -   This MUST be the first object in the `structure` array.
        -   For its `styles` object, add properties for fixed position, top/left/right of 0, a high zIndex, padding, and a backdropFilter for a glassmorphism effect.
        -   Its `children` array should contain one `column` object. This column should have flexbox styles to space its children apart.
        -   The column's children should be a `text` element for the logo and another `column` for navigation `button`s.
    5.  **HERO SECTION (`type: 'section'`):**
        -   This MUST be the second object in the `structure` array.
        -   For its `styles` object, give it a minHeight of "90vh", and use flexbox to center its content both vertically and horizontally. It must have a relative position.
        -   Add a `special` object inside it with one property: `animatedBlobs` with the string value "true".
        -   Its `children` array should contain one `column` object which contains a profile `image` (with a circular border-radius and a glow-like boxShadow), a main `heading` (use a large, clamped font size), a `text` subheading, and another `column` with two `button`s inside.
    6.  **OTHER CONTENT SECTIONS (`type: 'section'`):**
        -   Style these with significant vertical padding.
        -   To create multi-column card layouts, make the section's child a `column` and give it grid styles, like `display: "grid"`, `gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))"`, and a `gap`.
        -   Generate relevant `heading`, `text`, and `image` elements for each section based on the user's request.
    7.  **ALL ELEMENTS:**
        -   Every object (section, column, element) MUST have a unique string `id`.
        -   Every element MUST have a `type`, `content` (string), and a `styles` object.
    8.  **JSON VALIDATION RULE:** Before outputting, double-check that every key and every string value is enclosed in double quotes. Ensure there are no trailing commas. The output must be ONLY the raw JSON object and nothing else.

    ---
    Now, generate the complete and perfectly valid JSON for the user's request: "{description}".
    """

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.8,
            "topP": 0.95,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
        }
    }

    try:
        result = api_call_with_backoff(api_url, headers={'Content-Type': 'application/json'}, payload=payload)
        response_text = result['candidates'][0]['content']['parts'][0]['text']
        website_data = json.loads(response_text)

        def traverse_and_process(node):
            if isinstance(node, dict):
                if node.get('type') == 'image' and 'content' in node and 'src' not in node:
                    node['src'] = f"https://placehold.co/600x400/0f172a/e5e7eb?text={node['content'].replace(' ', '+')}"
                if 'id' not in node:
                    node['id'] = f"node-{int(time.time() * 10000) + hash(str(node))}"
                for value in node.values():
                    traverse_and_process(value)
            elif isinstance(node, list):
                for item in node:
                    traverse_and_process(item)
        
        traverse_and_process(website_data)
        
        return jsonify(website_data)

    except Exception as e:
        print(f"Error during website JSON generation: {e}")
        return jsonify({"error": f"Failed to generate website structure: {str(e)}"}), 500


@app.route('/preview')
def preview():
    """Displays the generated website in an editor interface."""
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>AI Website Editor</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;900&family=Poppins:wght@400;700&family=Roboto:wght@400;700&display=swap" rel="stylesheet">
            <style>
                body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #e2e8f0; overflow: hidden;}
                .editor-container { display: grid; grid-template-columns: 1fr 380px; height: 100vh; }
                .main-canvas { display: flex; flex-direction: column; background-color: #1e293b; }
                .properties-panel { background-color: #0f172a; padding: 1rem; overflow-y: auto; border-left: 1px solid #334155; }
                .top-toolbar { background-color: #1e293b; padding: 0.5rem 1rem; border-bottom: 1px solid #334155; flex-shrink: 0; }
                .iframe-wrapper { flex-grow: 1; padding: 1.5rem; background-color: #030712; }
                #editor-frame { width: 100%; height: 100%; border: 1px solid #334155; background-color: white; border-radius: 0.5rem; transition: all 0.3s ease; }
                .panel-section details { margin-bottom: 1rem; border-radius: 0.5rem; background-color: #1e293b; }
                .panel-section summary { font-weight: 600; color: #94a3b8; padding: 0.75rem; cursor: pointer; }
                .panel-section div { padding: 0.75rem; }
                .prop-label { font-size: 0.875rem; color: #cbd5e1; margin-bottom: 0.25rem; display: block; }
                .prop-input, .prop-select, .prop-textarea { width: 100%; background-color: #334155; border: 1px solid #475569; color: white; border-radius: 0.375rem; padding: 0.5rem; font-size: 0.875rem; }
                .prop-input[type="color"] { padding: 0.125rem; height: 38px; }
                .selected-in-frame { outline: 3px solid #38bdf8 !important; outline-offset: 2px; box-shadow: 0 0 20px rgba(56, 189, 248, 0.5); }
                .danger-btn { background-color: #be123c; color: white; border: none; padding: 0.5rem 1rem; border-radius: 0.375rem; font-weight: 500; cursor: pointer; margin-top: 1rem; text-align: center; display: block; width: 100%; }
            </style>
        </head>
        <body>
            <div id="editor-container" class="editor-container">
                <!-- Main Canvas & Toolbar -->
                <div class="main-canvas">
                    <div class="top-toolbar flex items-center justify-between">
                        <div class="flex items-center gap-4">
                            <h2 class="text-lg font-bold text-white">Live Editor</h2>
                            <a href="/" class="text-sm text-slate-400 hover:text-white transition">← Start Over</a>
                        </div>
                        <div class="flex items-center gap-3">
                           <button id="downloadBtn" class="bg-indigo-600 text-white text-sm font-bold py-2 px-4 rounded-lg hover:bg-indigo-700">Download HTML</button>
                        </div>
                    </div>
                    <div class="iframe-wrapper">
                        <iframe id="editor-frame"></iframe>
                    </div>
                </div>
                <!-- Properties Panel -->
                <div id="properties-panel" class="properties-panel"></div>
            </div>
            <script>
                let websiteData = {};
                let selectedElementId = null;

                document.addEventListener('DOMContentLoaded', () => {
                    const storedData = sessionStorage.getItem('websiteData');
                    if (storedData) {
                        websiteData = JSON.parse(storedData);
                        renderWebsiteInFrame();
                        renderPropertiesPanel();
                    } else {
                        document.body.innerHTML = '<div class="text-center text-white text-2xl p-8">No website data found. Please <a href="/" class="underline">start over</a>.</div>';
                        return;
                    }
                    document.getElementById('downloadBtn').addEventListener('click', downloadHTML);
                });
                
                function findNodeAndParent(id, nodes = websiteData.structure, parent = null) {
                    for (const node of nodes) {
                        if (node.id === id) return { node, parent };
                        if (node.children) {
                            const found = findNodeAndParent(id, node.children, node);
                            if (found) return found;
                        }
                    }
                    return null;
                }

                function renderWebsiteInFrame() {
                    const frame = document.getElementById('editor-frame');
                    const { globalStyles, structure } = websiteData;
                    const googleFont = globalStyles.fontFamily.split(',')[0].replace(/'/g, "").replace(/\s/g, '+');

                    function buildHtmlAndStyles(nodes) {
                        let html = '';
                        nodes.forEach(node => {
                            const tag = { nav: 'nav', section: 'section', column: 'div', heading: 'h2', text: 'p', button: 'button', image: 'img' }[node.type] || 'div';
                            
                            let inlineStyle = '';
                            if(node.styles) {
                                for (const [key, value] of Object.entries(node.styles)) {
                                    const cssKey = key.replace(/[A-Z]/g, letter => `-${letter.toLowerCase()}`);
                                    inlineStyle += `${cssKey}: ${value}; `;
                                }
                            }
                            
                            let specialHtml = '';
                            if(node.special?.animatedBlobs === "true") {
                                specialHtml += `
                                <div style="position:absolute; z-index: -1; top:-8rem; left:-8rem; width:16rem; height:16rem; background-color:${globalStyles.primaryColor}; border-radius:9999px; mix-blend-mode:lighten; filter:blur(3rem); opacity:0.2; animation:blob-anim 10s infinite;"></div>
                                <div style="position:absolute; z-index: -1; bottom:-8rem; right:-8rem; width:16rem; height:16rem; background-color:${globalStyles.accentColor}; border-radius:9999px; mix-blend-mode:lighten; filter:blur(3rem); opacity:0.2; animation:blob-anim 10s infinite reverse;"></div>
                                `;
                            }

                            if (node.type !== 'image') {
                                html += `<${tag} id="${node.id}" style="${inlineStyle}" class="editable-element">`;
                                html += specialHtml;
                                html += node.content || '';
                                if (node.children) {
                                    html += buildHtmlAndStyles(node.children);
                                }
                                html += `</${tag}>`;
                            } else {
                                html += `<img id="${node.id}" src="${node.src}" alt="${node.content || ''}" style="${inlineStyle}" class="editable-element">`
                            }
                        });
                        return html;
                    }

                    const bodyHtml = buildHtmlAndStyles(structure);

                    const finalHtml = `
                    <html><head>
                        <script src="https://cdn.tailwindcss.com"><\/script>
                        <link href="https://fonts.googleapis.com/css2?family=${googleFont}:wght@400;500;700;900&display=swap" rel="stylesheet">
                        <style>
                            html { scroll-behavior: smooth; }
                            body { 
                                font-family: ${globalStyles.fontFamily}; 
                                background-color: ${globalStyles.backgroundColor}; 
                                color: ${globalStyles.textColor}; 
                                margin: 0; padding: 0; 
                                ${globalStyles.special?.bgGrid === "true" ? `background-image: linear-gradient(to right, rgba(200, 200, 200, 0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(200, 200, 200, 0.05) 1px, transparent 1px); background-size: 2rem 2rem;` : ''}
                            }
                            .editable-element { cursor: pointer; transition: outline 0.2s; position: relative; }
                            [contenteditable]:focus, [contenteditable]:hover { outline: 2px dashed #38bdf8 !important; }
                            img.editable-element:hover { outline: 2px dashed #38bdf8; }
                            @keyframes blob-anim { 50% { transform: scale(1.2) translate(20px, -30px); } }
                        </style>
                    </head><body><main class="mx-auto">${bodyHtml}</main></body></html>`;

                    frame.srcdoc = finalHtml;
                    frame.onload = () => {
                        const frameDoc = frame.contentDocument;
                        frameDoc.querySelectorAll('.editable-element').forEach(el => {
                            el.addEventListener('click', (e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                window.parent.postMessage({ type: 'elementSelected', id: el.id }, '*');
                            });
                            if(['H2', 'P', 'BUTTON'].includes(el.tagName)) {
                                el.contentEditable = true;
                                el.addEventListener('blur', (e) => {
                                    window.parent.postMessage({ type: 'contentChanged', id: el.id, newContent: el.innerHTML }, '*');
                                });
                            }
                        });
                    };
                }

                function renderPropertiesPanel() {
                    const panel = document.getElementById('properties-panel');
                    const result = selectedElementId ? findNodeAndParent(selectedElementId) : null;
                    const selectedElement = result ? result.node : null;

                    let content = '<div class="p-2">';

                    if (selectedElement) {
                        content += `<h2 class="text-lg font-bold mb-4 text-white">${selectedElement.type.charAt(0).toUpperCase() + selectedElement.type.slice(1)} Properties</h2><div class="space-y-4">`;
                        
                        // Content Editing
                        if ('content' in selectedElement) {
                           content += createTextareaControl('Content', 'content', selectedElement.content || '');
                        }
                        if (selectedElement.type === 'image') {
                           content += createTextControl('Image Source (URL)', 'src', selectedElement.src || '');
                        }
                        
                        // Styling
                        if ('styles' in selectedElement) {
                            content += `<details open class="panel-section"><summary>Styling</summary><div>`;
                            for(const styleProp in selectedElement.styles) {
                                if(styleProp.toLowerCase().includes('color')) {
                                    content += createColorControl(styleProp, `styles.${styleProp}`, selectedElement.styles[styleProp]);
                                } else {
                                    content += createTextControl(styleProp, `styles.${styleProp}`, selectedElement.styles[styleProp]);
                                }
                            }
                            content += `</div></details>`;
                        }

                        // Add Child Element
                        if (selectedElement.type === 'column') {
                           content += `<details class="panel-section"><summary>Add Element</summary><div><div class="grid grid-cols-2 gap-2">
                           <button class="prop-input" data-action="addChild" data-child-type="heading">Heading</button>
                           <button class="prop-input" data-action="addChild" data-child-type="text">Text</button>
                           <button class="prop-input" data-action="addChild" data-child-type="button">Button</button>
                           <button class="prop-input" data-action="addChild" data-child-type="image">Image</button>
                           </div></div></details>`;
                        }
                        
                        // Delete Element
                        content += `<button class="danger-btn" data-action="delete">Delete Element</button>`;
                        content += `</div>`;
                    } else {
                         content += `<h2 class="text-lg font-bold mb-4 text-white">Global Styles</h2><div class="space-y-3 mt-2">`;
                         content += createFontSelect('Font Family', 'globalStyles.fontFamily', websiteData.globalStyles.fontFamily);
                         content += createColorControl('Background', 'globalStyles.backgroundColor', websiteData.globalStyles.backgroundColor);
                         content += createColorControl('Text', 'globalStyles.textColor', websiteData.globalStyles.textColor);
                         content += createColorControl('Primary', 'globalStyles.primaryColor', websiteData.globalStyles.primaryColor);
                         content += createColorControl('Accent', 'globalStyles.accentColor', websiteData.globalStyles.accentColor);
                         content += `</div>`;
                    }
                    content += '</div>';
                    panel.innerHTML = content;
                    addPanelEventListeners();
                }

                function createTextareaControl(label, key, value) { return `<div><label class="prop-label">${label}</label><textarea class="prop-textarea" data-key="${key}" rows="4">${value}</textarea></div>`; }
                function createTextControl(label, key, value) { return `<div><label class="prop-label">${label}</label><input type="text" class="prop-input" data-key="${key}" value="${value || ''}"></div>`; }
                function createColorControl(label, key, value) { return `<div><label class="prop-label">${label}</label><div class="flex items-center gap-2"><input type="color" class="prop-input w-10 h-10 p-1" data-key="${key}" value="${value || '#ffffff'}"><input type="text" class="prop-input" data-key="${key}" value="${value || ''}"></div></div>`; }
                function createFontSelect(label, key, value) {
                    const fonts = ["'Inter', sans-serif", "'Poppins', sans-serif", "'Roboto', sans-serif"];
                    let options = fonts.map(f => `<option value="${f}" ${f === value ? 'selected' : ''}>${f.split(',')[0].replace(/'/g, '')}</option>`).join('');
                    return `<div><label class="prop-label">${label}</label><select class="prop-select" data-key="${key}">${options}</select></div>`;
                }
                
                function addPanelEventListeners() {
                    document.querySelectorAll('#properties-panel [data-key]').forEach(input => {
                        input.addEventListener('input', handlePropertyChange);
                    });
                     document.querySelectorAll('#properties-panel [data-action]').forEach(button => {
                        button.addEventListener('click', handleAction);
                    });
                }
                
                function handlePropertyChange(e) {
                    const keyPath = e.target.dataset.key;
                    const value = e.target.value;
                    
                    const setProperty = (obj, path, val) => {
                        const keys = path.split('.');
                        const lastKey = keys.pop();
                        const lastObj = keys.reduce((o, k) => {
                            if(o[k] === undefined) o[k] = {};
                            return o[k];
                        }, obj);
                        lastObj[lastKey] = val;
                    };
                    
                    if (keyPath.startsWith('globalStyles')) {
                        setProperty(websiteData, keyPath, value);
                    } else if (selectedElementId) {
                        const { node } = findNodeAndParent(selectedElementId);
                        if (node) setProperty(node, keyPath, value);
                    }
                    saveAndRerender();
                }

                function handleAction(e) {
                    const action = e.target.dataset.action;
                    if (action === 'delete') {
                        deleteSelectedElement();
                    }
                    if (action === 'addChild') {
                        const childType = e.target.dataset.childType;
                        addChildElement(childType);
                    }
                }

                function deleteSelectedElement() {
                    if (!selectedElementId) return;
                    const { node, parent } = findNodeAndParent(selectedElementId);
                    if (!parent || !parent.children) return;
                    parent.children = parent.children.filter(child => child.id !== selectedElementId);
                    selectedElementId = null;
                    saveAndRerender();
                    renderPropertiesPanel();
                }

                function addChildElement(type) {
                    if (!selectedElementId) return;
                    const { node } = findNodeAndParent(selectedElementId);
                    if (node && node.type === 'column') {
                        if(!node.children) node.children = [];
                        const newElement = {
                            id: `el-${Date.now()}`,
                            type: type,
                            content: `New ${type}`,
                            styles: type === 'button' ? { padding: '0.5rem 1rem', background: websiteData.globalStyles.primaryColor, borderRadius: '0.5rem'} : {}
                        };
                         if (type === 'image') {
                           newElement.src = 'https://placehold.co/600x400/0f172a/e5e7eb?text=New+Image'
                        }
                        node.children.push(newElement);
                        saveAndRerender();
                    } else {
                        alert("You can only add new elements to a 'column' type.")
                    }
                }

                window.addEventListener('message', (event) => {
                    const { type, id, newContent } = event.data;
                    if (type === 'elementSelected') {
                        selectedElementId = id;
                        renderPropertiesPanel();
                        const frameDoc = document.getElementById('editor-frame').contentDocument;
                        frameDoc.querySelectorAll('.selected-in-frame').forEach(el => el.classList.remove('selected-in-frame'));
                        const selectedEl = frameDoc.getElementById(id);
                        if(selectedEl) selectedEl.classList.add('selected-in-frame');
                    } else if (type === 'contentChanged') {
                        const { node } = findNodeAndParent(id);
                        if(node) {
                            node.content = newContent;
                            saveAndRerender();
                        }
                    }
                });
                
                function saveAndRerender() {
                    sessionStorage.setItem('websiteData', JSON.stringify(websiteData));
                    renderWebsiteInFrame();
                     setTimeout(() => {
                        if (selectedElementId) {
                            const frameDoc = document.getElementById('editor-frame').contentDocument;
                             const selectedEl = frameDoc.getElementById(selectedElementId);
                             if(selectedEl) selectedEl.classList.add('selected-in-frame');
                        }
                    }, 150);
                }

                function downloadHTML() {
                    const finalHtml = document.getElementById('editor-frame').srcdoc;
                    const blob = new Blob([finalHtml], { type: 'text/html' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'index.html';
                    a.click();
                    URL.revokeObjectURL(url);
                }
            </script>
        </body>
        </html>
    ''')

if __name__ == '__main__':
    app.run(debug=True, port=5001)
