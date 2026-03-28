
import os
import mysql.connector
from flask import Flask, send_file, send_from_directory, request, jsonify, session, redirect, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure Uploads
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database Configuration
def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Hatdog555",  # User should update this if necessary
            database="anatomy_quiz_game"
        )
        return connection
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    return send_file('frontends/dashboard.html')

@app.route('/api/user-profile')
def get_user_profile():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT email, firstname, lastname, birth_date, educational_level, gender, image_path, unlocked_level FROM user_accounts WHERE user_id = %s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if user:
        return jsonify(user)
    return jsonify({"error": "User not found"}), 404

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        # Check if email already exists
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM user_accounts WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Email already exists"}), 400
        
        cursor.close()
        conn.close()

        # Store in session instead of database
        session['signup_email'] = email
        session['signup_password'] = password
        return jsonify({"success": True})
            
    return send_file('frontends/signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT user_id, password FROM user_accounts WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user and user['password'] == password:
            session['user_id'] = user['user_id']
            return jsonify({"success": True})
        return jsonify({"error": "Invalid email or password"}), 401
        
    return send_file('frontends/index.html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if request.method == 'POST':
        data = request.json
        firstname = data.get('firstName')
        lastname = data.get('lastName')
        birth_date = data.get('birthDate')
        gender = data.get('gender')
        education = data.get('education')

        # Check if we are in a signup flow (user_id not in session but signup_email is)
        is_signup = 'user_id' not in session and 'signup_email' in session
        
        # Mapping gender to ENUM values
        gender_map = {
            'male': 'Male',
            'female': 'Female',
            'other': 'Other',
            'nonbinary': 'Other',
            'prefer-not': 'Other'
        }
        db_gender = gender_map.get(gender, 'Other')
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cursor = conn.cursor()
        try:
            if is_signup:
                # Create the account now
                cursor.execute(
                    "INSERT INTO user_accounts (email, password, firstname, lastname, birth_date, educational_level, gender) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (session['signup_email'], session['signup_password'], firstname, lastname, birth_date, education, db_gender)
                )
                conn.commit()
                session['user_id'] = cursor.lastrowid
                # Clear signup session data
                session.pop('signup_email', None)
                session.pop('signup_password', None)
            else:
                # Standard profile update for existing user
                if 'user_id' not in session:
                    return jsonify({"error": "Not logged in"}), 401
                
                cursor.execute(
                    "UPDATE user_accounts SET firstname = %s, lastname = %s, birth_date = %s, educational_level = %s, gender = %s WHERE user_id = %s",
                    (firstname, lastname, birth_date, education, db_gender, session['user_id'])
                )
                conn.commit()
            
            return jsonify({"success": True})
        except mysql.connector.Error as err:
            return jsonify({"error": str(err)}), 400
        finally:
            cursor.close()
            conn.close()
            
    return send_file('frontends/profile.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('signin'))

@app.route('/api/upload-profile-image', methods=['POST'])
def upload_profile_image():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(f"user_{session['user_id']}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Save to database
        db_path = f"/uploads/{filename}"
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor()
        cursor.execute("UPDATE user_accounts SET image_path = %s WHERE user_id = %s", (db_path, session['user_id']))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"success": True, "image_path": db_path})
    
    return jsonify({"error": "File type not allowed"}), 400

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/dashboard.css')
def dashboard_css():
    return send_file('frontends/dashboard.css')

@app.route('/')
def root_loading():
    return send_file('frontends/loading.html')

@app.route('/style.css')
def style():
    return send_file('frontends/style.css')

@app.route('/signup.css')
def signup_style():
    return send_file('frontends/signup.css')

@app.route('/loading')
def loading():
    return send_file('frontends/loading.html')

@app.route('/loading.css')
def loading_css():
    return send_file('frontends/loading.css')

@app.route('/demographic', methods=['GET', 'POST'])
def demographic():
    return profile()

@app.route('/demographic.css')
def demographic_css():
    return send_file('frontends/demographic.css')

@app.route('/profile.css')
def profile_css():
    return send_file('frontends/profile.css')

@app.route('/api/update-progress', methods=['POST'])
def update_progress():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.json
    new_level = data.get('level')
    
    if not new_level:
        return jsonify({"error": "No level provided"}), 400
        
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
        
    try:
        cursor = conn.cursor()
        # Only update if the new level is higher than the current unlocked level
        cursor.execute("UPDATE user_accounts SET unlocked_level = GREATEST(unlocked_level, %s) WHERE user_id = %s", (new_level, session['user_id']))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": True})
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500

@app.route('/api/questions')
def get_questions():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    topic = request.args.get('topic', '').lower()
    category = request.args.get('category', 'Multiple Choice')
    
    # Map dashboard topic names to database table names
    topic_to_table = {
        "integumentary": "integumentary",
        "skeletal": "skeletal",
        "muscular": "muscular",
        "digestive": "digestive",
        "respiratory": "respiratory",
        "cardiovascular": "cardiovascular",
        "reproductive": "reproductive",
        "nervous": "nervous"
    }
    
    table_name = topic_to_table.get(topic)
    if not table_name:
        return jsonify({"error": "Invalid topic"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        # Select 10 random questions from the specific table and category
        query = f"SELECT questions, option_a, option_b, option_c, option_d, answer FROM {table_name} WHERE category = %s ORDER BY RAND() LIMIT 10"
        cursor.execute(query, (category,))
        questions = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(questions)
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500

@app.route('/quiz')
def quiz():
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    return send_file('frontends/quiz.html')

@app.route('/quiz.css')
def quiz_css():
    return send_file('frontends/quiz.css')

@app.route('/images/<path:filename>')
def images(filename):
    return send_from_directory('images', filename)

if __name__ == '__main__':
    app.run(debug=True)