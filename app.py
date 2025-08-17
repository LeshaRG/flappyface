from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import sqlite3
import os
from werkzeug.utils import secure_filename
import uuid
from OpenSSL import SSL

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database setup
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE, photo_path TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scores
                 (id INTEGER PRIMARY KEY, user_id INTEGER, score INTEGER,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    conn.commit()
    conn.close()

init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # Get top 10 scores with user info
    c.execute('''SELECT u.name, u.photo_path, MAX(s.score) as max_score
                 FROM users u JOIN scores s ON u.id = s.user_id
                 GROUP BY u.id ORDER BY max_score DESC LIMIT 10''')
    top_scores = c.fetchall()
    conn.close()
    return render_template('index.html', top_scores=top_scores)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['name']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT id, photo_path FROM users WHERE name = ?', (name,))
        user = c.fetchone()
        if user:
            session['user_id'] = user[0]
            session['photo_path'] = user[1]
            return redirect(url_for('game'))
        else:
            # New user, redirect to capture photo
            session['new_user_name'] = name
            return redirect(url_for('capture_photo'))
    return render_template('login.html')

@app.route('/capture_photo')
def capture_photo():
    if 'new_user_name' not in session:
        return redirect(url_for('login'))
    return render_template('capture_photo.html')

@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    if 'new_user_name' not in session:
        return redirect(url_for('login'))

    if 'photo' not in request.files:
        return redirect(url_for('capture_photo'))

    file = request.files['photo']
    if file and allowed_file(file.filename):
        filename = secure_filename(str(uuid.uuid4()) + '.png')
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('INSERT INTO users (name, photo_path) VALUES (?, ?)',
                  (session['new_user_name'], 'uploads/' + filename))
        user_id = c.lastrowid
        conn.commit()
        conn.close()

        session['user_id'] = user_id
        session['photo_path'] = 'uploads/' + filename
        session.pop('new_user_name', None)

        # ✅ сразу редирект в игру
        return redirect(url_for('game'))

    return redirect(url_for('capture_photo'))

@app.route('/game')
def game():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # если фото не загружено или нет пользователя
    return render_template('game.html', photo_path=session['photo_path'])

@app.route('/save_score', methods=['POST'])
def save_score():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    score = request.json.get('score')
    if score is not None:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('INSERT INTO scores (user_id, score) VALUES (?, ?)',
                  (session['user_id'], score))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    return jsonify({'error': 'No score provided'}), 400

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
