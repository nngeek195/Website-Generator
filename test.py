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
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=180)
            # Raise an exception for bad status codes (4xx or 5xx)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"API call failed with HTTPError (retry {i+1}/{max_retries}): {e}")
            # For specific client errors like 400, it might not be worth retrying.
            if e.response.status_code == 400:
                print("Bad request, not retrying.")
                # You might want to log the payload here for debugging
                # print("Failing Payload:", payload)
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
    # This HTML is the user interface for inputting the website topic.
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
                    <textarea id="description" class="w-full bg-slate-900 border-2 border-slate-700 rounded-lg p-4 mb-6 text-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-300" rows="4" placeholder="e.g., A portfolio for a freelance photographer named Jane Doe specializing in nature photography."></textarea>
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
                        const response = await fetch('/generate_website', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ description })
                        });

                        if (!response.ok) {
                            const errorData = await response.json();
                            throw new Error(errorData.error || 'An unknown error occurred.');
                        }

                        const result = await response.json();
                        // Store result in session storage and redirect to the preview page
                        sessionStorage.setItem('websiteHTML', result.html);
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


@app.route('/generate_website', methods=['POST'])
def generate_website():
    """
    Receives the website description, calls the Gemini API to generate
    the full HTML, and returns it.
    """
    data = request.get_json()
    description = data.get('description')

    if not description:
        return jsonify({"error": "No description provided"}), 400
    if not GEMINI_API_KEY:
         return jsonify({"error": "API key is not configured on the server."}), 500


    # This is the new, powerful prompt that instructs the AI to generate a full website
    # based on the high-quality portfolio example.
    prompt = f"""
        You are an expert web designer who creates stunning, responsive, single-page websites using HTML and Tailwind CSS.
        Your task is to generate a complete HTML file based on the user's request.

        **CRITICAL INSTRUCTIONS:**
        1.  **Frameworks:** Use HTML and Tailwind CSS. Load Tailwind via the official CDN: `<script src="https://cdn.tailwindcss.com"></script>`.
        2.  **Structure & Style:** Emulate the provided "World-Class Portfolio" example. This means:
            - A dark, modern theme (e.g., `bg-gray-900`, `text-gray-200`).
            - A fixed navigation bar at the top.
            - A large, impactful "Hero" section that takes up most of the screen.
            - Multiple content sections (like "Services", "Features", "About", "Gallery").
            - A final "Contact" section.
            - A simple footer.
        3.  **Responsiveness:** Ensure the design is fully responsive and looks great on mobile, tablet, and desktop. Use flexbox and grid (`flex`, `grid`, `md:grid-cols-2`, etc.).
        4.  **Content Generation:** Based on the user's description, generate relevant and engaging text content for all sections. **DO NOT** use placeholder text like "Lorem Ipsum".
        5.  **Images:** Use placeholder images from `https://placehold.co/`. The image URLs should be descriptive. For example: `<img src="https://placehold.co/600x400/1e293b/ffffff?text=Nature+Shot" alt="Relevant Alt Text">`.
        6.  **Icons:** Use Font Awesome for icons. Load it via CDN: `<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">`.
        7.  **Font:** Use the 'Inter' font from Google Fonts.
        8.  **Output:** Provide **ONLY** the complete, raw HTML code for a single `.html` file. Do not include any explanations, markdown formatting, or anything other than the code itself.

        ---
        **USER'S WEBSITE REQUEST:**
        "{description}"
        ---

        Now, generate the complete HTML code based on all the instructions above.
    """

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.95,
            "maxOutputTokens": 8192,
        }
    }

    try:
        result = api_call_with_backoff(api_url, headers={'Content-Type': 'application/json'}, payload=payload)
        
        # Extract the generated HTML content
        generated_text = result['candidates'][0]['content']['parts'][0]['text']
        
        # Clean the response to ensure it's pure HTML
        if generated_text.strip().startswith("```html"):
            generated_text = generated_text[7:]
        if generated_text.strip().endswith("```"):
            generated_text = generated_text[:-3]

        return jsonify({"html": generated_text.strip()})

    except Exception as e:
        print(f"Error during website generation: {e}")
        return jsonify({"error": f"Failed to communicate with the AI model: {str(e)}"}), 500


@app.route('/preview')
def preview():
    """Displays the generated website and provides a download button."""
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Website Preview</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-slate-800">
            <div class="fixed top-0 left-0 right-0 bg-slate-900/80 backdrop-blur-sm shadow-lg z-50 p-4 flex justify-between items-center">
                <h1 class="text-xl text-white font-bold">Preview</h1>
                <div>
                    <a href="/" class="text-white bg-slate-600 hover:bg-slate-700 font-medium py-2 px-4 rounded-lg transition mr-2">Start Over</a>
                    <button id="downloadBtn" class="text-white bg-blue-600 hover:bg-blue-700 font-bold py-2 px-4 rounded-lg transition">Download HTML</button>
                </div>
            </div>
            <iframe id="preview-frame" class="w-full h-screen border-none mt-[72px]"></iframe>
            <script>
                document.addEventListener('DOMContentLoaded', () => {
                    const htmlContent = sessionStorage.getItem('websiteHTML');
                    if (htmlContent) {
                        const frame = document.getElementById('preview-frame');
                        frame.srcdoc = htmlContent;
                    } else {
                        document.body.innerHTML = '<div class="text-center text-white text-2xl p-8">No website content found. Please go back and generate a website first.</div>';
                    }

                    document.getElementById('downloadBtn').addEventListener('click', () => {
                        const html = sessionStorage.getItem('websiteHTML');
                        if (html) {
                            const blob = new Blob([html], { type: 'text/html' });
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = 'website.html';
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            URL.revokeObjectURL(url);
                        } else {
                            alert("No HTML content to download.");
                        }
                    });
                });
            </script>
        </body>
        </html>
    ''')

if __name__ == '__main__':
    # Use port 5001 as requested in the original code
    app.run(debug=True, port=5001)
