import requests
import os

url = 'http://127.0.0.1:5000/upload'
file_path = r'C:\Users\bradw\.gemini\antigravity\brain\57fc7157-6cbb-4f66-8bec-37ac55a366aa\uploaded_image_1764209659832.png'

with open(file_path, 'rb') as f:
    files = {'files': f}
    response = requests.post(url, files=files, allow_redirects=False)

if response.status_code == 302:
    redirect_url = response.headers['Location']
    print(f"Redirect URL: {redirect_url}")
    session_id = redirect_url.split('/')[-1]
    print(f"Session ID: {session_id}")
    
    # Trigger processing
    process_url = f'http://127.0.0.1:5000/process/{session_id}'
    print(f"Triggering processing at: {process_url}")
    process_response = requests.get(process_url)
    print(f"Process Status: {process_response.status_code}")
    print(f"Process Response: {process_response.text[:200]}...")
else:
    print(f"Upload failed with status: {response.status_code}")
    print(response.text)
