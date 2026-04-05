from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import ForeignKeyConstraint, and_

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(50), nullable=False)
    lastname = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    school = db.Column(db.String(120))
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.subject_id', name='fk_user_subject'), nullable=True)
    role = db.Column(db.String(20), default='student')  # 'student' or 'teacher'
    student_class = db.Column(db.String(50), nullable=True)  # For students only
    student_id = db.Column(db.String(20), unique=True, nullable=True)  # Unique student ID like STU2026001
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    
    examResults = db.relationship('ExamResult', backref='user', lazy=True)
    
class Subject(db.Model):
    subject_id = db.Column(db.Integer, primary_key=True)
    subject_name = db.Column(db.String(100), unique=True, nullable=False)
    
    def __repr__(self):
        return f'<Subject {self.subject_name}>'


class Topic(db.Model):
    topic_id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.subject_id', name='fk_topic_subject'), nullable=False)
    topic_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    Subject = db.relationship('Subject', backref=db.backref('topics', lazy=True))
    
    __table_args__ = (
        db.UniqueConstraint('subject_id', 'topic_name', name='uq_subject_topic'),
    )
    
    def __repr__(self):
        return f'<Topic {self.topic_name} for {self.Subject.subject_name}>'
    
    
class ExamSession(db.Model):
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.subject_id', name='fk_examsession_subject'), primary_key=True)
    session_id = db.Column(db.String(100), primary_key=True)
    exam_session = db.Column(db.String(100), nullable=False)
    
    Subject = db.relationship('Subject', backref=db.backref('exam_sessions', lazy=True))
    
    def __repr__(self):
        return f'<ExamSession {self.exam_session} for subject_id={self.subject_id}>'

class ExamResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_examresult_user'), nullable=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.subject_id', name='fk_examresult_subject'), nullable=False)
    session_id = db.Column(db.String(100), nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    student_id = db.Column(db.String(20), nullable=True)  # Unique student ID like STU2026001
    student_class = db.Column(db.String(50))
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    submitted_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    __table_args__ = (
        db.ForeignKeyConstraint(
            ['subject_id', 'session_id'],
            ['exam_session.subject_id', 'exam_session.session_id'],
            name='fk_examresult_exam_session'
        ),
    )

    Subject = db.relationship('Subject', backref=db.backref('exam_results', lazy=True))

    def __repr__(self):
        return f'<ExamResult {self.student_name} - {self.percentage}%>'

class StudentAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_result_id = db.Column(db.Integer, db.ForeignKey('exam_result.id', name='fk_studentanswer_examresult'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', name='fk_studentanswer_question'), nullable=False)
    student_answer = db.Column(db.String(1), nullable=False)  # A, B, C, or D
    is_correct = db.Column(db.Boolean, default=False)
    
    ExamResult = db.relationship('ExamResult', backref=db.backref('student_answers', lazy=True))
    Question = db.relationship('Question', backref=db.backref('student_answers', lazy=True))
    
    def __repr__(self):
        return f'<StudentAnswer Q{self.question_id}: {self.student_answer}>'

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_image = db.Column(db.String(500), nullable=True)  # Path to uploaded image
    question_type = db.Column(db.String(20), default='multiple_choice')  # 'multiple_choice' or 'true_false'
    option_a = db.Column(db.String(500), nullable=True)  # Can be None for true/false questions
    option_b = db.Column(db.String(500), nullable=True)  # Can be None for true/false questions
    option_c = db.Column(db.String(500), nullable=True)  # Can be None for true/false questions
    option_d = db.Column(db.String(500), nullable=True)  # Can be None for true/false questions
    correct_answer = db.Column(db.String(1), nullable=False)  # A, B, C, D for multiple choice; T or F for true/false
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.subject_id', name='fk_question_subject'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.topic_id', name='fk_question_topic'), nullable=True)
    session_id = db.Column(db.String(100), nullable=False)
    __table_args__ = (
    db.ForeignKeyConstraint(
        ['subject_id', 'session_id'],
        ['exam_session.subject_id', 'exam_session.session_id'],
        name='fk_question_exam_session'
    ),
)
    
    Subject = db.relationship('Subject', backref=db.backref('questions', lazy=True))
    Topic = db.relationship('Topic', backref=db.backref('questions', lazy=True))
    ExamSession = db.relationship('ExamSession', primaryjoin="and_(Question.subject_id==ExamSession.subject_id, Question.session_id==ExamSession.session_id)", viewonly=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def __repr__(self):
        return f'<Question {self.id}: {self.question_text[:50]}...>'

    @property
    def subject(self):
        return self.Subject.subject_name if self.Subject else None

    @property
    def session(self):
        return self.ExamSession.exam_session if self.ExamSession else None