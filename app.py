import pandas as pd
import os
import random
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'uploads'

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# In-memory mock database (replace with a real database in production)
users = {}
schedules = {}

# Routes
@app.route('/')
def index():
    if 'email' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        if email in users and check_password_hash(users[email]['password'], password):
            session['email'] = email
            flash("Login successful!", "success")
            return redirect(url_for('home'))
        flash("Invalid email or password. Please try again.", "danger")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('email', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']

        if email not in users:
            users[email] = {'full_name': full_name, 'password': generate_password_hash(password)}
            session['email'] = email
            flash("Account created successfully! Welcome to AutoSchedule.", "success")
            return redirect(url_for('home'))
        else:
            flash("Email is already registered. Please log in.", "danger")
    
    return render_template('signup.html', title="Sign Up")

@app.route('/home')
def home():
    if 'email' not in session:
        return redirect(url_for('login'))
    user = users.get(session['email'])
    return render_template('home.html', user=user)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'email' not in session:
        return redirect(url_for('login'))
    user = users.get(session['email'])
    if request.method == 'POST':
        # Handle form submission to update user settings (e.g., password, name)
        new_name = request.form['full_name']
        users[session['email']]['full_name'] = new_name
        flash("Settings updated successfully.", "success")
    return render_template('settings.html', user=user)



@app.route('/schedule', methods=['GET', 'POST'])
def schedule():
    if 'email' not in session:
        return redirect(url_for('login'))
    
    schedule_files = []

    if request.method == 'POST':
        if 'bulk_file' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        file = request.files['bulk_file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        
        try:
            df = pd.read_csv(filepath) if file.filename.endswith('.csv') else pd.read_excel(filepath)

            # Check for required columns
            required_columns = ['Department', 'Faculty', 'Subject', 'Room', 'Type', 'Lab']
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                flash(f"Error: Missing columns in the file: {', '.join(missing_columns)}", 'danger')
                return redirect(request.url)

            # Generate schedules
            departments = df['Department'].unique()
            for department in departments:
                department_data = df[df['Department'] == department]
                department_schedule_file = generate_schedule(department_data, department)
                schedule_files.append(department_schedule_file)
            
            flash("Schedules generated successfully! You can download them below.", "success")
            return render_template('schedule.html', schedule_files=schedule_files)
        
        except Exception as e:
            flash(f"Error generating schedule: {e}", 'danger')
    
    return render_template('schedule.html', schedule_files=schedule_files)

def generate_schedule(df, department):
    # Handle missing 'Type' column
    if 'Type' not in df.columns:
        df['Type'] = 'Lecture'  # Default to 'Lecture' for all rows

    # Handle missing 'Lab' column
    if 'Lab' not in df.columns:
        df['Lab'] = ''  # Default to empty for all rows

    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    hours = ['9:00-10:00', '10:00-11:00', '11:00-12:00', '1:00-2:00', '2:00-4:00']

    # Separate lectures and practicals
    practicals = df[df['Type'] == 'Practical']
    lectures = df[df['Type'] == 'Lecture']

    # Ensure each lecture is paired with a practical
    if len(lectures) > len(practicals):
        raise ValueError("Number of lectures exceeds number of practicals. Each lecture must have a practical.")

    # Prepare the schedule DataFrame
    schedule = pd.DataFrame(index=days, columns=hours)

    # Pair lectures with practicals in alternating slots
    practical_slots = ['9:00-10:00', '2:00-4:00']  # Morning and afternoon slots for practicals
    lecture_slots = ['10:00-11:00', '11:00-12:00', '1:00-2:00']  # Midday slots for lectures

    for day in days:
        if not lectures.empty and not practicals.empty:
            # Assign practical in morning or afternoon
            practical = practicals.sample(1)
            practicals = practicals.drop(practical.index)
            slot = practical_slots.pop(0)
            practical_slots.append(slot)
            schedule.at[day, slot] = f"{practical.iloc[0]['Faculty']} ({practical.iloc[0]['Subject']}) - {practical.iloc[0]['Lab']}"
            
            # Assign corresponding lecture to the next available slot
            lecture = lectures.sample(1)
            lectures = lectures.drop(lecture.index)
            lecture_slot = lecture_slots.pop(0)
            lecture_slots.append(lecture_slot)
            schedule.at[day, lecture_slot] = f"{lecture.iloc[0]['Faculty']} ({lecture.iloc[0]['Subject']}) - {lecture.iloc[0]['Room']}"

    # Save schedule
    schedule_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{department}_schedule.xlsx')
    schedule.to_excel(schedule_path)
    return f'{department}_schedule.xlsx'

@app.route('/download_schedule/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
   app.run(host="0.0.0.0", port=5000, debug=True)

