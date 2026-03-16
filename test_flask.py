# test_flask.py
from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return """
    <h1>🎉 Flask is Working!</h1>
    <p>Your sticky-note web app will run here.</p>
    <p>Close this window and press Ctrl+C in terminal to stop.</p>
    """

if __name__ == '__main__':
    print("🚀 Starting test web server...")
    print("📱 Open browser to: http://localhost:5000")
    print("⏹️  Press Ctrl+C to stop")
    app.run(debug=True, port=5000)