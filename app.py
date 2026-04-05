from flask import Flask, request, jsonify, render_template, url_for, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, ExamResult, Question, Subject, ExamSession, StudentAnswer, Topic
from flask_migrate import Migrate
from functools import wraps
from datetime import datetime
from sqlalchemy import and_, or_
import os
from pathlib import Path

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'your-secret-key'

# File upload configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Create upload folder if it doesn't exist
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db.init_app(app)
Migrate(app, db)


# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return render_template('student_home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form.get('role', 'student')
        firstname = request.form.get('firstname')
        lastname = request.form.get('lastname')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        school = request.form.get('school') 
        student_class = request.form.get('student_class')
        subject = request.form.get('subject')
        
        # Validation
        if not all([firstname, lastname, email, password, confirm_password]):
            return render_template('register.html', error='All fields are required')
        
        if role == 'student' and not student_class:
            return render_template('register.html', error='Class is required for student registration')
        if role == 'teacher' and not subject:
            return render_template('register.html', error='Subject is required for teacher registration')
        
        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match')
        
        if len(password) < 8:
            return render_template('register.html', error='Password must be at least 8 characters')
        
        # Check if email exists
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='Email already registered')
        
        # Create new user
        try:
            subj_id = None
            student_id = None
            
            if role == 'teacher' and subject:
                s = Subject.query.filter(db.func.lower(Subject.subject_name) == subject.strip().lower()).first()
                if not s:
                    s = Subject(subject_name=subject.strip())
                    db.session.add(s)
                    db.session.flush()
                subj_id = s.subject_id
            elif role == 'student':
                # Generate student ID
                import random
                import string
                while True:
                    # Generate a unique student ID (e.g., STU2026001)
                    year = datetime.now().year
                    random_num = ''.join(random.choices(string.digits, k=3))
                    student_id = f"STU{year}{random_num}"
                    if not User.query.filter_by(student_id=student_id).first():
                        break
            
            new_user = User(
                firstname=firstname,
                lastname=lastname,
                email=email,
                password_hash=generate_password_hash(password),
                school=school,
                subject_id=subj_id,
                role=role,
                student_id=student_id,
                student_class=student_class if role == 'student' else None
            )
            db.session.add(new_user)
            db.session.commit()
            
            # Registration successful - redirect to login
            return redirect(url_for('login'))
                
        except Exception as e:
            db.session.rollback()
            return render_template('register.html', error=f'An error occurred: {str(e)}')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember')
        
        if not email or not password:
            return render_template('login.html', error='Email and password are required')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['firstname'] = user.firstname
            session['email'] = user.email
            session['role'] = user.role
            if user.student_id:
                session['student_id'] = user.student_id
            
            # Redirect based on role
            if user.role == 'teacher':
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('home'))
        else:
            return render_template('login.html', error='Invalid email or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/cbt')
@login_required
def cbt_interface():
    # Get subject_id and session from query parameters
    subject_id = request.args.get('subject_id')
    exam_session = request.args.get('session')
    
    # Get logged-in student's name
    student_firstname = session.get('firstname', '')
    student_id = session.get('student_id', '')
    
    # Fetch all subjects for dropdown
    subjects = Subject.query.all()
    subjects_list = [{'subject_id': s.subject_id, 'subject_name': s.subject_name} for s in subjects]
    
    # Fetch all exam sessions or filter by subject_id if provided
    if subject_id:
        try:
            subject_id = int(subject_id)
            available_sessions = ExamSession.query.filter_by(subject_id=subject_id).all()
            sessions_list = [[es.session_id, es.exam_session] for es in available_sessions]
        except (ValueError, TypeError):
            sessions_list = []
    else:
        exam_sessions = ExamSession.query.all()
        sessions_list = [[es.session_id, es.exam_session] for es in exam_sessions]
    
    # Pass to template
    return render_template('cbt_interface.html', 
                         subjects=subjects_list, 
                         sessions=sessions_list,
                         subject_id=subject_id,
                         session=exam_session,
                         student_name=student_firstname,
                         student_id=student_id)

@app.route('/api/submit-exam', methods=['POST'])
def submit_exam():
    data = request.get_json()

    if not data or 'student_name' not in data or 'score' not in data:
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        student_name = data.get('student_name')
        student_class = data.get('student_class', '')
        subject_name = data.get('subject')
        session_name = data.get('session')
        correct = data.get('score')  # number of correct answers
        total = data.get('total_questions', 0)
        percentage = data.get('percentage', 0)
        answers = data.get('answers', [])  # Array of student answers

        if not subject_name:
            return jsonify({'error': 'Subject is required'}), 400

        # Look up subject_id
        subj = Subject.query.filter(db.func.lower(Subject.subject_name) == subject_name.strip().lower()).first()
        if not subj:
            return jsonify({'error': f'Subject not found: {subject_name}'}), 400

        # Look up session_id
        session_id = None
        if session_name:
            session_id = session_name.strip().replace(' ', '_').lower()
            exam_session = ExamSession.query.filter_by(subject_id=subj.subject_id, session_id=session_id).first()
            if not exam_session:
                return jsonify({'error': f'Exam session not found: {session_name}'}), 400

        # For anonymous submissions, user_id is None
        # For teacher-submitted results, user_id would be set
        user_id = session.get('user_id') if 'user_id' in session else None
        student_id = session.get('student_id') if 'student_id' in session else None

        # Create exam result record
        result = ExamResult(
            user_id=user_id,
            subject_id=subj.subject_id,
            session_id=session_id,
            student_name=student_name,
            student_id=student_id,
            student_class=student_class,
            score=correct,
            total_questions=total,
            percentage=percentage
        )

        db.session.add(result)
        db.session.flush()  # Get the result ID

        # Store individual student answers
        if answers:
            for idx, answer_data in enumerate(answers):
                if isinstance(answer_data, dict):
                    question_id = answer_data.get('question_id')
                    student_answer = answer_data.get('answer')
                    is_correct = answer_data.get('is_correct', False)
                else:
                    # Assume it's just the answer letter if not a dict
                    question_id = idx + 1
                    student_answer = answer_data
                    is_correct = False

                if question_id and student_answer:
                    student_ans = StudentAnswer(
                        exam_result_id=result.id,
                        question_id=question_id,
                        student_answer=student_answer,
                        is_correct=is_correct
                    )
                    db.session.add(student_ans)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Exam result submitted successfully',
            'result_id': result.id
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    user = User.query.get(user_id)

    if user.role == 'teacher':
        # Get all questions created by this teacher
        teacher_questions = Question.query.filter_by(user_id=user_id).all()
        
        # Extract unique (subject_id, session_id) pairs from teacher's questions
        exam_sessions_created = set((q.subject_id, q.session_id) for q in teacher_questions)
        
        # If teacher has no exams, show empty results
        if not exam_sessions_created:
            results = []
        else:
            # Filter ExamResults to only those from the teacher's exams
            filters = [
                and_(ExamResult.subject_id == subj_id, ExamResult.session_id == sess_id)
                for subj_id, sess_id in exam_sessions_created
            ]
            results = ExamResult.query.filter(or_(*filters)).order_by(ExamResult.submitted_at.desc()).all()
    else:
        # regular student sees only their own results
        results = ExamResult.query.filter(ExamResult.user_id == user_id).order_by(ExamResult.submitted_at.desc()).all()

    total_exams = len(results)
    total_students = len(set(r.student_name for r in results))
    average_score = sum(r.percentage for r in results) / total_exams if total_exams > 0 else 0
    pass_rate = sum(1 for r in results if r.percentage >= 50) / total_exams * 100 if total_exams > 0 else 0
    
    stats = {
        'total_exams': total_exams,
        'total_students': total_students,
        'average_score': average_score,
        'pass_rate': pass_rate
    }
    return render_template('dashboard.html', results=results, stats=stats)

@app.route('/api/result/<int:result_id>', methods=['GET'])
@login_required
def get_result_details(result_id):
    """Get detailed information about a specific exam result with all questions and answers"""
    result = ExamResult.query.get(result_id)
    
    if not result:
        return jsonify({'error': 'Result not found'}), 404
    
    # Get all questions from this exam session
    questions = Question.query.filter_by(
        subject_id=result.subject_id,
        session_id=result.session_id
    ).all()
    
    # Get student's answers
    student_answers = StudentAnswer.query.filter_by(exam_result_id=result_id).all()
    student_answers_dict = {sa.question_id: sa for sa in student_answers}
    
    # Build question details with student answers
    question_details = []
    for q in questions:
        student_ans = student_answers_dict.get(q.id)
        question_details.append({
            'id': q.id,
            'question_text': q.question_text,
            'option_a': q.option_a,
            'option_b': q.option_b,
            'option_c': q.option_c,
            'option_d': q.option_d,
            'correct_answer': q.correct_answer,
            'student_answer': student_ans.student_answer if student_ans else None,
            'is_correct': student_ans.is_correct if student_ans else False
        })
    
    return jsonify({
        'student_name': result.student_name,
        'student_class': result.student_class,
        'student_id': result.student_id,
        'subject': result.Subject.subject_name if result.Subject else 'N/A',
        'score': result.score,
        'total_questions': result.total_questions,
        'percentage': result.percentage,
        'submitted_at': result.submitted_at.isoformat() if result.submitted_at else None,
        'questions': question_details
    }), 200

@app.route('/student-dashboard')
@login_required
def student_dashboard():
    user_id = session['user_id']
    user = User.query.get(user_id)
    if user.role != 'student':
        return redirect(url_for('dashboard'))  # Redirect teachers to teacher dashboard
    
    # Get student's exam results
    results = ExamResult.query.filter_by(user_id=user_id).order_by(ExamResult.submitted_at.desc()).all()
    
    # Calculate stats
    total_exams = len(results)
    average_score = sum(r.percentage for r in results) / total_exams if total_exams > 0 else 0
    highest_score = max((r.percentage for r in results), default=0)
    pass_rate = sum(1 for r in results if r.percentage >= 50) / total_exams * 100 if total_exams > 0 else 0
    
    # Group results by subject
    exams_by_subject = {}
    for result in results:
        subject_name = result.Subject.subject_name if result.Subject else 'Unknown'
        if subject_name not in exams_by_subject:
            exams_by_subject[subject_name] = []
        exams_by_subject[subject_name].append(result)
    
    stats = {
        'total_exams': total_exams,
        'average_score': average_score,
        'highest_score': highest_score,
        'pass_rate': pass_rate
    }
    
    return render_template('student_dashboard.html', results=results, stats=stats, exams_by_subject=exams_by_subject)

@app.route('/api/get-topics/<int:subject_id>', methods=['GET'])
def get_topics(subject_id):
    """Get all topics for a specific subject"""
    try:
        topics = Topic.query.filter_by(subject_id=subject_id).all()
        topics_data = [
            {
                'id': t.topic_id,
                'name': t.topic_name,
                'description': t.description
            }
            for t in topics
        ]
        return jsonify({'success': True, 'topics': topics_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/debug/subjects', methods=['GET'])
def debug_subjects():
    """Debug endpoint to check all subjects and their topics"""
    try:
        subjects = Subject.query.all()
        data = []
        for subj in subjects:
            topics = Topic.query.filter_by(subject_id=subj.subject_id).all()
            data.append({
                'subject_id': subj.subject_id,
                'subject_name': subj.subject_name,
                'topic_count': len(topics),
                'topics': [{'id': t.topic_id, 'name': t.topic_name} for t in topics]
            })
        return jsonify({'success': True, 'subjects': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/debug/seed-topics', methods=['POST'])
def seed_topics():
    """Debug endpoint to seed sample topics (for testing only)"""
    try:
        # Sample topics for common subjects
        sample_topics = {
            'Mathematics': ['Algebra', 'Geometry', 'Calculus', 'Statistics', 'Trigonometry'],
            'Physics': ['Mechanics', 'Thermodynamics', 'Electricity', 'Magnetism', 'Optics'],
            'Chemistry': ['Organic Chemistry', 'Inorganic Chemistry', 'Physical Chemistry', 'Biochemistry'],
            'Biology': ['Cell Biology', 'Genetics', 'Ecology', 'Evolution', 'Anatomy'],
            'English Literature': ['Poetry', 'Prose', 'Drama', 'Literary Criticism'],
            'Computer Science': ['Programming', 'Algorithms', 'Data Structures', 'Databases', 'Web Development'],
            'History': ['Ancient History', 'Medieval History', 'Modern History', 'World Wars'],
            'Economics': ['Microeconomics', 'Macroeconomics', 'International Trade', 'Development Economics'],
        }
        
        created_count = 0
        for subject_name, topics in sample_topics.items():
            # Find or create subject
            subject = Subject.query.filter_by(subject_name=subject_name).first()
            if not subject:
                subject = Subject(subject_name=subject_name)
                db.session.add(subject)
                db.session.flush()
            
            # Add topics for this subject
            for topic_name in topics:
                # Check if topic already exists
                exists = Topic.query.filter_by(subject_id=subject.subject_id, topic_name=topic_name).first()
                if not exists:
                    topic = Topic(
                        subject_id=subject.subject_id,
                        topic_name=topic_name,
                        description=f"{topic_name} topic for {subject_name}"
                    )
                    db.session.add(topic)
                    created_count += 1
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'Created {created_count} topics'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/select-subject-session', methods=['GET', 'POST'])
def select_subject_session():
    is_student_flow = request.args.get('student') == 'true' or request.form.get('is_student') == 'true'
    subject_id_param = request.args.get('subject_id')
    
    if request.method == 'POST':
        subject_id = request.form.get('subject')
        session_id = request.form.get('session')
        topic_name = request.form.get('topic_name')
        is_student_submission = request.form.get('is_student') == 'true'
        
        if not subject_id or not session_id:
            all_subjects = Subject.query.all()
            available_sessions = []
            if subject_id:
                available_sessions = ExamSession.query.filter_by(subject_id=subject_id).all()
            context = {
                'all_subjects': all_subjects,
                'available_sessions': available_sessions,
                'error': 'Both subject and session are required',
                'is_student': is_student_submission,
                'selected_subject_id': int(subject_id) if subject_id else None
            }
            return render_template('select_subject_session.html', **context)
        
        # Get the subject object
        subject_obj = Subject.query.get(subject_id)
        if not subject_obj:
            all_subjects = Subject.query.all()
            available_sessions = ExamSession.query.filter_by(subject_id=subject_id).all() if subject_id else []
            context = {
                'all_subjects': all_subjects,
                'available_sessions': available_sessions,
                'error': 'Invalid subject selected',
                'is_student': is_student_submission,
                'selected_subject_id': int(subject_id) if subject_id else None
            }
            return render_template('select_subject_session.html', **context)
        
        # If student flow, redirect to CBT interface with subject_id and session_id
        if is_student_submission:
            return redirect(url_for('cbt_interface', subject_id=subject_id, session=session_id))
        
        # Otherwise redirect to questions page (teacher flow)
        params = {'subject': subject_obj.subject_name, 'session': session_id, 'subject_id': subject_id}
        if topic_name:
            params['topic_name'] = topic_name
        return redirect(url_for('add_questions', **params))
    
    # GET request - show the form
    all_subjects = Subject.query.all()
    available_sessions = []
    selected_subject_id = None
    
    if subject_id_param:
        selected_subject_id = int(subject_id_param)
        # Get available sessions for this subject
        available_sessions = ExamSession.query.filter_by(subject_id=selected_subject_id).all()
    
    context = {
        'all_subjects': all_subjects,
        'available_sessions': available_sessions,
        'is_student': is_student_flow,
        'selected_subject_id': selected_subject_id
    }
    return render_template('select_subject_session.html', **context)

@app.route('/add-questions')
@login_required
def add_questions():
    subject = request.args.get('subject')
    subject_id = request.args.get('subject_id', type=int)
    session_year = request.args.get('session')
    topic_name = request.args.get('topic_name')
    error = request.args.get('error')
    success = request.args.get('success')
    
    if not subject or not session_year or not subject_id:
        return redirect(url_for('select_subject_session'))
    
    # Get existing questions for this subject and session
    session_id = session_year.strip().replace(' ', '_').lower()
    user_questions = Question.query.filter_by(
        user_id=session['user_id'],
        subject_id=subject_id,
        session_id=session_id
    ).order_by(Question.created_at.desc()).all()
    
    return render_template('add_questions.html', 
                         subject=subject, 
                         subject_id=subject_id,
                         session_year=session_year,
                         topic_name=topic_name,
                         questions=user_questions,
                         error=error,
                         success=success)

@app.route('/questions')
@login_required
def questions():
    user_id = session['user_id']
    user_questions = Question.query.filter_by(user_id=user_id).order_by(Question.created_at.desc()).all()
    
    # Group questions by session
    questions_by_session = {}
    for question in user_questions:
        session_key = question.session or 'No Session'
        if session_key not in questions_by_session:
            questions_by_session[session_key] = []
        questions_by_session[session_key].append(question)
    
    # Sort sessions (put 'No Session' at the end)
    sorted_sessions = {}
    no_session_questions = questions_by_session.pop('No Session', [])
    
    # Sort other sessions by name (assuming they are years like "2023/2024")
    for session_name in sorted(questions_by_session.keys(), reverse=True):
        sorted_sessions[session_name] = questions_by_session[session_name]
    
    # Add 'No Session' at the end if it exists
    if no_session_questions:
        sorted_sessions['No Session'] = no_session_questions
    
    return render_template('questions.html', questions_by_session=sorted_sessions, total_questions=len(user_questions))

@app.route('/add-question', methods=['POST'])
@login_required
def add_question():
    if request.method == 'POST':
        subject = request.form.get('subject')
        session_year = request.form.get('session_year')
        topic_name = request.form.get('topic_name')
        question_text = request.form.get('question_text')
        question_type = request.form.get('question_type', 'multiple_choice')
        correct_answer = request.form.get('correct_answer')
        
        # Handle based on question type
        if question_type == 'multiple_choice':
            option_a = request.form.get('option_a')
            option_b = request.form.get('option_b')
            option_c = request.form.get('option_c')
            option_d = request.form.get('option_d')
            
            # Validation for multiple choice
            if not all([question_text, option_a, option_b, option_c, option_d, correct_answer, subject, session_year]):
                return jsonify({'success': False, 'error': 'All fields are required for multiple choice questions'})
            
            if correct_answer not in ['A', 'B', 'C', 'D']:
                return jsonify({'success': False, 'error': 'Invalid correct answer. Must be A, B, C, or D'})
        
        elif question_type == 'true_false':
            option_a = 'True'
            option_b = 'False'
            option_c = None
            option_d = None
            
            # Validation for true/false
            if not all([question_text, correct_answer, subject, session_year]):
                return jsonify({'success': False, 'error': 'All required fields must be filled for true/false questions'})
            
            if correct_answer not in ['T', 'F']:
                return jsonify({'success': False, 'error': 'Invalid correct answer. Must be T or F'})
        else:
            return jsonify({'success': False, 'error': 'Invalid question type'})

        try:
            # Handle image upload
            question_image = None
            if 'question_image' in request.files:
                file = request.files['question_image']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Add timestamp to make filename unique
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                    filename = timestamp + filename
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    question_image = f"uploads/{filename}"

            # Ensure Subject exists (case-insensitive)
            subj = Subject.query.filter(db.func.lower(Subject.subject_name) == subject.strip().lower()).first()
            if not subj:
                subj = Subject(subject_name=subject.strip())
                db.session.add(subj)
                db.session.flush()  # get subj.subject_id

            # Create or get Topic if topic_name is provided
            topic_obj = None
            if topic_name and topic_name.strip():
                topic_name = topic_name.strip()
                topic_obj = Topic.query.filter_by(
                    subject_id=subj.subject_id,
                    topic_name=topic_name
                ).first()
                if not topic_obj:
                    topic_obj = Topic(
                        subject_id=subj.subject_id,
                        topic_name=topic_name,
                        description=f"{topic_name} for {subject}"
                    )
                    db.session.add(topic_obj)
                    db.session.flush()

            # Create or get ExamSession for this subject
            # session_id: normalized id for lookup
            session_id = session_year.strip().replace(' ', '_').lower()
            exam_sess = ExamSession.query.filter_by(subject_id=subj.subject_id, session_id=session_id).first()
            if not exam_sess:
                exam_sess = ExamSession(subject_id=subj.subject_id, session_id=session_id, exam_session=session_year.strip())
                db.session.add(exam_sess)

            # Create question linked to subject and session, with optional topic
            new_question = Question(
                user_id=session['user_id'],
                question_text=question_text,
                question_image=question_image,
                question_type=question_type,
                option_a=option_a,
                option_b=option_b,
                option_c=option_c,
                option_d=option_d,
                correct_answer=correct_answer,
                subject_id=subj.subject_id,
                session_id=exam_sess.session_id,
                topic_id=topic_obj.topic_id if topic_obj else None
            )

            db.session.add(new_question)
            db.session.commit()

            return jsonify({'success': True, 'message': 'Question added successfully!'})

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': f'Failed to add question: {str(e)}'})


@app.route('/delete-question/<int:question_id>', methods=['DELETE'])
@login_required
def delete_question(question_id):
    question = Question.query.filter_by(id=question_id, user_id=session['user_id']).first()

    if not question:
        return jsonify({'success': False, 'error': 'Question not found'}), 404

    try:
        db.session.delete(question)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Question deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/available-exams')
def get_available_exams():
    try:
        # Aggregate questions by subject (include subject_id for session lookup)
        subjects_query = db.session.query(Subject.subject_id, Subject.subject_name, db.func.count(Question.id).label('question_count')).join(Question, Question.subject_id == Subject.subject_id).group_by(Subject.subject_id, Subject.subject_name).all()

        exams = {}
        for subject_id, subject_name, question_count in subjects_query:
            if subject_name and question_count > 0:
                # Count distinct teachers for this subject
                teacher_count = db.session.query(db.func.count(db.distinct(Question.user_id))).filter(Question.subject_id == subject_id).scalar()

                # Get available sessions for this subject
                sessions_q = db.session.query(ExamSession.session_id, ExamSession.exam_session).filter(ExamSession.subject_id == subject_id).all()
                sessions = [{'session_id': s[0], 'exam_session': s[1]} for s in sessions_q]

                exams[subject_name] = {
                    'subject_id': subject_id,
                    'question_count': question_count,
                    'teacher_count': teacher_count,
                    'sessions': sessions
                }

        return jsonify({
            'success': True,
            'exams': exams
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/get-questions')
def get_questions():
    try:
        subject = request.args.get('subject')
        session_param = request.args.get('session')
        limit = request.args.get('limit', 100, type=int)  # Max 100 questions at a time
        
        print(f"[DEBUG] get-questions called with subject: {subject}, session: {session_param}")
        
        if not subject:
            return jsonify({
                'success': False,
                'error': 'Subject parameter is required'
            }), 400
        
        # Query questions by subject (join with Subject)
        subj = Subject.query.filter(db.func.lower(Subject.subject_name) == subject.strip().lower()).first()
        if not subj:
            return jsonify({'success': False, 'error': f'Subject not found: {subject}'}), 404

        # Build query
        q = Question.query.filter_by(subject_id=subj.subject_id)
        if session_param:
            # normalize session id
            session_id = session_param.strip().replace(' ', '_').lower()
            q = q.filter_by(session_id=session_id)
        
        # Limit results to prevent timeout
        q = q.limit(limit)
        questions = q.all()
        print(f"[DEBUG] Found {len(questions)} questions for subject: {subject}, session: {session_param}")
        
        if not questions:
            # Try listing available subjects
            all_subjects = db.session.query(Subject.subject_name).distinct().all()
            print(f"[DEBUG] Available subjects: {[s[0] for s in all_subjects]}")
            return jsonify({
                'success': False,
                'error': f'No questions found for subject: {subject}',
                'available_subjects': [s[0] for s in all_subjects]
            }), 404
        
        # Format questions for response
        questions_data = []
        for q in questions:
            # Convert correct_answer from letter (A, B, C, D, T, F) to string
            correct_answer = q.correct_answer
            
            questions_data.append({
                'id': q.id,
                'question_text': q.question_text,
                'question_image': q.question_image,
                'question_type': q.question_type or 'multiple_choice',
                'option_a': q.option_a,
                'option_b': q.option_b,
                'option_c': q.option_c,
                'option_d': q.option_d,
                'correct_answer': correct_answer,
                'subject': q.subject,
                'session': q.session
            })
        
        print(f"[DEBUG] Returning {len(questions_data)} formatted questions")
        return jsonify({
            'success': True,
            'subject': subject,
            'questions': questions_data,
            'count': len(questions_data)
        }), 200
        
    except Exception as e:
        print(f"[DEBUG] Error in get_questions: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sessions/<int:subject_id>')
def get_sessions_by_subject(subject_id):
    """Get available exam sessions for a specific subject"""
    try:
        sessions = ExamSession.query.filter_by(subject_id=subject_id).all()
        sessions_list = [
            {
                'session_id': session.session_id,
                'exam_session': session.exam_session
            }
            for session in sessions
        ]
        return jsonify({
            'success': True,
            'sessions': sessions_list
        }), 200
    except Exception as e:
        print(f"[DEBUG] Error fetching sessions: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Student Exam Routes
@app.route('/student/exams/<int:subject_id>/<session_id>')
@login_required
def student_exams_select(subject_id, session_id):
    """Student selects a subject and exam session"""
    try:
        subjects = Subject.query.all()
        subject_id = Subject.query.get(subject_id).subject_id if Subject.query.get(subject_id) else None
        sessions = db.session.query(ExamSession.session_id, ExamSession.exam_session).distinct().all()
        
        print(f"[DEBUG] Loaded {len(subjects)} subjects and {len(sessions)} sessions")
        
        return render_template('student_exams.html', subjects=subjects,subject_id = subject_id, sessions=sessions)
    except Exception as e:
        print(f"[ERROR] in student_exams_select: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template('student_exams.html', subjects=[], sessions=[], error=str(e))

@app.route('/student/exam-mode/<int:subject_id>/<session_id>')
@login_required
def student_exam_mode(subject_id, session_id):
    """Student chooses between topic-specific or full subject exam"""
    try:
        print(f"[DEBUG] Exam mode route called: subject_id={subject_id}, session_id={session_id}")
        
        subject = Subject.query.get(subject_id)
        if not subject:
            print(f"[DEBUG] Subject not found: {subject_id}")
            return redirect(url_for('student_exams_select'))
        
        print(f"[DEBUG] Found subject: {subject.subject_name}")
        
        topics = db.session.query(Topic).filter_by(subject_id=subject_id).all()
        print(f"[DEBUG] Found {len(topics)} topics for subject {subject_id}")
        
        return render_template('student_exam_mode.html', 
                             subject=subject, 
                             session_id=session_id, 
                             topics=topics)
    except Exception as e:
        print(f"[ERROR] in student_exam_mode: {str(e)}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('student_exams_select'))

@app.route('/student/exam/<int:subject_id>/<session_id>')
@login_required
def student_take_full_exam(subject_id, session_id):
    """Student takes a full subject exam"""
    subject = Subject.query.get(subject_id)
    if not subject:
        return redirect(url_for('student_exams_select'))
    
    questions = Question.query.filter_by(subject_id=subject_id, session_id=session_id).all()
    if not questions:
        return redirect(url_for('student_exam_mode', subject_id=subject_id, session_id=session_id))
    
    return render_template('student_take_exam.html', 
                         subject=subject, 
                         session_id=session_id, 
                         questions=questions, 
                         exam_type='full')

@app.route('/student/exam-topic/<int:topic_id>/<session_id>')
@login_required
def student_take_topic_exam(topic_id, session_id):
    """Student takes a topic-specific exam"""
    topic = Topic.query.get(topic_id)
    if not topic:
        return redirect(url_for('student_exams_select'))
    
    questions = Question.query.filter_by(topic_id=topic_id, session_id=session_id).all()
    if not questions:
        return redirect(url_for('student_exam_mode', subject_id=topic.subject_id, session_id=session_id))
    
    return render_template('student_take_exam.html',
                         topic=topic,
                         subject=topic.Subject,
                         session_id=session_id,
                         questions=questions,
                         exam_type='topic')

@app.route('/student/submit-exam', methods=['POST'])
@login_required
def student_submit_exam():
    """Submit exam answers and calculate results"""
    subject_id = request.form.get('subject_id', type=int)
    session_id = request.form.get('session_id')
    exam_type = request.form.get('exam_type', 'full')
    topic_id = request.form.get('topic_id', type=int)
    
    if not subject_id or not session_id:
        return redirect(url_for('student_exams_select'))
    
    subject = Subject.query.get(subject_id)
    if not subject:
        return redirect(url_for('student_exams_select'))
    
    user = User.query.get(session['user_id'])
    
    # Get questions based on exam type
    if exam_type == 'topic' and topic_id:
        questions = Question.query.filter_by(topic_id=topic_id, session_id=session_id).all()
    else:
        questions = Question.query.filter_by(subject_id=subject_id, session_id=session_id).all()
    
    # Calculate score
    score = 0
    student_answers = []
    
    for question in questions:
        answer_key = f'question_{question.id}'
        student_answer = request.form.get(answer_key)
        
        if student_answer:
            is_correct = student_answer == question.correct_answer
            if is_correct:
                score += 1
            
            student_answers.append({
                'question_id': question.id,
                'student_answer': student_answer,
                'is_correct': is_correct
            })
    
    return redirect(url_for('student_dashboard'))

# New Routes for Full Exam vs Practice Mode Workflow
@app.route('/exam-mode-selection')
@login_required
def exam_mode_selection():
    """Page where student selects between Full Exam and Practice Mode"""
    subject_id = request.args.get('subject_id')
    session_id = request.args.get('session')
    
    subject = Subject.query.get(subject_id) if subject_id else None
    if not subject:
        return redirect(url_for('cbt_interface'))
    
    # Verify session exists
    exam_session = ExamSession.query.filter_by(subject_id=subject_id, session_id=session_id).first()
    if not exam_session:
        return redirect(url_for('cbt_interface'))
    
    return render_template('exam_mode_selection.html')

@app.route('/practice-mode')
@login_required
def practice_mode():
    """Page where student selects topics for practice mode"""
    subject_id = request.args.get('subject_id')
    session_id = request.args.get('session')
    
    subject = Subject.query.get(subject_id) if subject_id else None
    if not subject:
        return redirect(url_for('cbt_interface'))
    
    # Verify session exists
    exam_session = ExamSession.query.filter_by(subject_id=subject_id, session_id=session_id).first()
    if not exam_session:
        return redirect(url_for('cbt_interface'))
    
    return render_template('practice_mode.html')

@app.route('/practice-exam')
@login_required
def practice_exam():
    """Practice exam interface for selected topics"""
    subject_id = request.args.get('subject_id')
    session_id = request.args.get('session')
    
    subject = Subject.query.get(subject_id) if subject_id else None
    if not subject:
        return redirect(url_for('cbt_interface'))
    
    return render_template('practice_exam.html')

@app.route('/full-exam')
@login_required
def full_exam():
    """Full exam interface - displays exam directly without form"""
    subject_id = request.args.get('subject_id')
    session_id = request.args.get('session')
    
    subject = Subject.query.get(subject_id) if subject_id else None
    if not subject:
        return redirect(url_for('cbt_interface'))
    
    # Verify session exists
    exam_session = ExamSession.query.filter_by(subject_id=subject_id, session_id=session_id).first()
    if not exam_session:
        return redirect(url_for('cbt_interface'))
    
    # Get logged-in student's name
    student_firstname = session.get('firstname', '')
    student_id = session.get('student_id', '')
    
    return render_template('full_exam.html',
                         student_name=student_firstname,
                         student_id=student_id,
                         subject_id=subject_id,
                         subject_name=subject.subject_name,
                         session=session_id)

@app.route('/api/debug/subject/<int:subject_id>', methods=['GET'])
def debug_subject_data(subject_id):
    """Debug endpoint to see all topics and questions for a subject"""
    try:
        print(f"\n{'='*60}")
        print(f"[DEBUG] Checking Subject #{subject_id}")
        print(f"{'='*60}\n")
        
        # Get subject
        subject = Subject.query.get(subject_id)
        if not subject:
            return jsonify({'error': f'Subject {subject_id} not found'}), 404
        
        print(f"[DEBUG] Subject: {subject.subject_name}\n")
        
        # Get all topics for this subject
        topics = Topic.query.filter_by(subject_id=subject_id).all()
        print(f"[DEBUG] Total Topics for Subject {subject_id}: {len(topics)}")
        for t in topics:
            print(f"[DEBUG]   - Topic #{t.topic_id}: {t.topic_name}")
        
        # Get all questions for this subject
        all_questions = Question.query.filter_by(subject_id=subject_id).all()
        print(f"\n[DEBUG] Total Questions for Subject {subject_id}: {len(all_questions)}\n")
        
        # Group questions by topic_id
        questions_by_topic = {}
        for q in all_questions:
            tid = q.topic_id
            if tid not in questions_by_topic:
                questions_by_topic[tid] = []
            questions_by_topic[tid].append(q)
        
        print(f"[DEBUG] Questions grouped by topic_id:")
        for topic_id in sorted(questions_by_topic.keys(), key=lambda x: (x is None, x)):
            qcount = len(questions_by_topic[topic_id])
            print(f"[DEBUG]   Topic #{topic_id}: {qcount} questions")
            # Show first 2 questions for each topic
            for q in questions_by_topic[topic_id][:2]:
                print(f"[DEBUG]     Q#{q.id} (Session: {q.session_id}): {q.question_text[:60]}...")
        
        # Group by session
        print(f"\n[DEBUG] Questions grouped by session_id:")
        questions_by_session = {}
        for q in all_questions:
            sid = q.session_id
            if sid not in questions_by_session:
                questions_by_session[sid] = 0
            questions_by_session[sid] += 1
        
        for sid, count in sorted(questions_by_session.items()):
            print(f"[DEBUG]   Session '{sid}': {count} questions")
        
        print(f"\n{'='*60}\n")
        
        # Return as JSON for easy viewing
        return jsonify({
            'subject_id': subject_id,
            'subject_name': subject.subject_name,
            'topics_count': len(topics),
            'topics': [{'topic_id': t.topic_id, 'topic_name': t.topic_name} for t in topics],
            'questions_count': len(all_questions),
            'questions_by_topic': {str(k): len(v) for k, v in questions_by_topic.items()},
            'questions_by_session': questions_by_session
        }), 200
    
    except Exception as e:
        print(f"[ERROR] in debug_subject_data: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/practice-questions/<int:subject_id>', methods=['GET'])
def get_practice_questions(subject_id):
    """Get practice questions from selected topics"""
    try:
        topics_param = request.args.get('topics', '')
        session_param = request.args.get('session', '')
        
        print(f"[DEBUG] get_practice_questions called:")
        print(f"  subject_id: {subject_id}")
        print(f"  topics_param: {topics_param}")
        print(f"  session_param: {session_param}")
        
        if not topics_param or topics_param.strip() == '':
            print(f"[DEBUG] No topics provided")
            return jsonify({'error': 'No topics selected', 'topics_param': topics_param}), 400
        
        # Convert comma-separated topics to list
        try:
            topic_ids = [int(t.strip()) for t in topics_param.split(',') if t.strip()]
        except ValueError as e:
            print(f"[DEBUG] Invalid topic IDs: {e}")
            return jsonify({'error': 'Invalid topic IDs', 'topics_param': topics_param}), 400
        
        print(f"[DEBUG] Parsed topic_ids: {topic_ids}")
        
        if not topic_ids:
            return jsonify({'error': 'No valid topic IDs provided'}), 400
        
        # Normalize session ID (same as in /api/get-questions)
        normalized_session = None
        if session_param and session_param.strip():
            normalized_session = session_param.strip().replace(' ', '_').lower()
            print(f"[DEBUG] Normalized session: '{session_param}' -> '{normalized_session}'")
        else:
            print(f"[DEBUG] No session provided, will use None")
        
        # First, verify the subject exists
        subject = Subject.query.get(subject_id)
        if not subject:
            print(f"[DEBUG] Subject not found: {subject_id}")
            return jsonify({'error': f'Subject not found: {subject_id}'}), 404
        
        print(f"[DEBUG] Subject found: {subject.subject_name}")
        
        # Get ALL questions for this subject to debug
        all_subject_questions = Question.query.filter_by(subject_id=subject_id).all()
        print(f"[DEBUG] Total questions for subject {subject_id}: {len(all_subject_questions)}")
        
        # Show topic_id distribution
        if all_subject_questions:
            topic_id_dist = {}
            session_id_dist = {}
            for q in all_subject_questions:
                topic_id_dist[q.topic_id] = topic_id_dist.get(q.topic_id, 0) + 1
                session_id_dist[q.session_id] = session_id_dist.get(q.session_id, 0) + 1
            
            print(f"[DEBUG] Topic ID distribution in database:")
            for tid, count in sorted(topic_id_dist.items(), key=lambda x: (x[0] is None, x[0])):
                print(f"[DEBUG]   - Topic {tid}: {count} questions")
            
            print(f"[DEBUG] Session ID distribution in database:")
            for sid, count in sorted(session_id_dist.items(), key=lambda x: (x[0] is None, x[0])):
                print(f"[DEBUG]   - Session '{sid}': {count} questions")
            
            print(f"[DEBUG] Looking for questions with topic_id in {topic_ids} and session_id='{normalized_session}'")
        
        # Query questions for selected topics
        query = Question.query.filter(
            Question.subject_id == subject_id,
            Question.topic_id.in_(topic_ids)
        )
        
        # Filter by session only if provided
        if normalized_session:
            query = query.filter(Question.session_id == normalized_session)
            print(f"[DEBUG] Filtering by session: {normalized_session}")
        else:
            print(f"[DEBUG] No session filter - returning all matching topic questions")
        
        questions = query.all()
        
        print(f"[DEBUG] Found {len(questions)} questions with topic filter")
        
        # FALLBACK: If no topic-filtered questions found, use all questions for the session
        # This handles cases where questions aren't assigned to specific topics yet
        if not questions and normalized_session:
            print(f"[DEBUG] No topic-filtered questions found. Falling back to all questions for session '{normalized_session}'")
            questions = Question.query.filter(
                Question.subject_id == subject_id,
                Question.session_id == normalized_session
            ).all()
            print(f"[DEBUG] Fallback returned {len(questions)} questions for the session")
        elif not questions and not normalized_session:
            print(f"[DEBUG] No topic-filtered questions and no session provided. Falling back to all questions for subject")
            questions = Question.query.filter(
                Question.subject_id == subject_id
            ).all()
            print(f"[DEBUG] Fallback returned {len(questions)} questions for the subject")
        
        if len(questions) > 0:
            print(f"[DEBUG] First question: {questions[0].question_text[:50]}...")
            for q in questions[:3]:
                print(f"[DEBUG]   Q{q.id}: topic_id={q.topic_id}, session_id={q.session_id}")
        
        questions_data = [
            {
                'id': q.id,
                'question_text': q.question_text,
                'option_a': q.option_a,
                'option_b': q.option_b,
                'option_c': q.option_c,
                'option_d': q.option_d,
                'correct_answer': q.correct_answer
            }
            for q in questions
        ]
        
        print(f"[DEBUG] Returning {len(questions_data)} questions as JSON")
        return jsonify(questions_data), 200
    
    except Exception as e:
        print(f"[ERROR] in get_practice_questions: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

@app.route('/student/exam-results/<int:result_id>')
@login_required
def student_exam_results(result_id):
    """Display exam results"""
    exam_type = request.args.get('exam_type', 'full')
    result = ExamResult.query.get(result_id)
    
    if not result:
        return redirect(url_for('student_exams_select'))
    
    # Check user owns this result
    if result.user_id != session['user_id']:
        return redirect(url_for('student_exams_select'))
    
    answers = StudentAnswer.query.filter_by(exam_result_id=result_id).all()
    
    return render_template('student_exam_results.html',
                         result=result,
                         answers=answers,
                         exam_type=exam_type)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)