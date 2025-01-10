from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_pymongo import PyMongo
import uuid
import csv
from io import StringIO
from flask import Response

app = Flask(__name__)
app.secret_key = "your_secret_key"

# MongoDB Configuration
app.config["MONGO_URI"] = "mongodb://localhost:27017/forms_app"
mongo = PyMongo(app)

# Predefined Student Credentials
PREDEFINED_STUDENTS = {
    "s1": "p1",
    "s2": "p2",
    "s3": "p3"
}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin')
def admin_dashboard():
    forms = mongo.db.forms.find()
    return render_template('admin_dashboard.html', forms=forms)

@app.route('/create_form', methods=['GET', 'POST'])
def create_form():
    if request.method == 'POST':
        form_title = request.form['form_title']
        questions = []

        # Parse questions from the form
        question_texts = request.form.getlist('question_text')
        question_types = request.form.getlist('question_type')
        question_options = request.form.getlist('question_options')

        for i in range(len(question_texts)):
            question = {
                "text": question_texts[i],
                "type": question_types[i],
                "options": [opt.strip() for opt in question_options[i].split(',')] if question_types[i] in ['radio', 'checkbox'] else []
            }
            questions.append(question)

        form_id = str(uuid.uuid4())  # Unique ID for each form

        # Save form to the database
        mongo.db.forms.insert_one({
            "form_id": form_id,
            "title": form_title,
            "questions": questions
        })
        flash("Form created successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('create_form.html')

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Validate credentials
        if username in PREDEFINED_STUDENTS and PREDEFINED_STUDENTS[username] == password:
            session['student_username'] = username
            flash(f"Welcome, {username}!", "success")
            return redirect(url_for('student_dashboard'))
        else:
            flash("Invalid credentials, please try again.", "danger")

    return render_template('student_login.html')

@app.route('/student/dashboard')
def student_dashboard():
    if 'student_username' not in session:
        flash("Please log in first.", "danger")
        return redirect(url_for('student_login'))

    # Convert the cursor to a list
    forms = list(mongo.db.forms.find())
    student_submissions = mongo.db.submissions.find()
    return render_template('student_dashboard.html', forms=forms, submissions=student_submissions)


@app.route('/student/logout',methods=['POST'])
def student_logout():
    session.pop('student_username', None)
    flash("Logged out successfully.", "success")
    return redirect(url_for('student_login'))

@app.route('/fill_form/<form_id>', methods=['GET', 'POST'])
def fill_form(form_id):
    if 'student_username' not in session:
        flash("Please log in first.", "danger")
        return redirect(url_for('student_login'))

    form = mongo.db.forms.find_one({"form_id": form_id})
    student_id = session['student_username']  # Use username as student ID

    # Check if the student has already submitted this form
    if mongo.db.submissions.find_one({"form_id": form_id, "student_id": student_id}):
        flash("You have already filled this form!", "danger")
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        answers = []
        for question in form['questions']:
            if question['type'] == 'checkbox':
                answers.append(request.form.getlist(question['text']))
            else:
                answers.append(request.form.get(question['text']))
        mongo.db.submissions.insert_one({
            "form_id": form_id,
            "student_id": student_id,
            "answers": answers
        })
        flash("Form submitted successfully!", "success")
        return redirect(url_for('student_dashboard'))

    return render_template('fill_form.html', form=form)
@app.route('/admin/view_submissions')
def view_submissions():
    # Fetch all forms
    forms = list(mongo.db.forms.find())
    return render_template('view_submissions.html', forms=forms)

@app.route('/admin/form_submissions/<form_id>')
def form_submissions(form_id):
    # Fetch the form details and its submissions
    form = mongo.db.forms.find_one({"form_id": form_id})
    submissions = mongo.db.submissions.find({"form_id": form_id})
    return render_template('form_submissions.html', form=form, submissions=submissions)

@app.route('/admin/download_submissions/<form_id>')
def download_submissions(form_id):
    # Fetch the form and its submissions
    form = mongo.db.forms.find_one({"form_id": form_id})
    submissions = mongo.db.submissions.find({"form_id": form_id})

    # Prepare CSV data
    csv_output = StringIO()
    writer = csv.writer(csv_output)
    
    # Write headers
    headers = ["Student ID"] + [question['text'] for question in form['questions']]
    writer.writerow(headers)

    # Write submission rows
    for submission in submissions:
        row = [submission['student_id']]
        row.extend(submission['answers'])
        writer.writerow(row)

    # Generate response
    csv_output.seek(0)
    response = Response(csv_output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={form['title']}_submissions.csv"
    return response
if __name__ == '__main__':
    app.run(debug=True)
