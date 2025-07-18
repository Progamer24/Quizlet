import streamlit as st
import sqlite3
import datetime
import pandas as pd
import plotly.express as px
from pathlib import Path
import hashlib
import time

# Database setup
def init_db():
    db_path = Path("quiz_master.db")
    if not db_path.exists():
        conn = sqlite3.connect('quiz_master.db')
        c = conn.cursor()
        
        # Users table
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      username TEXT UNIQUE NOT NULL,
                      password TEXT NOT NULL,
                      full_name TEXT,
                      qualification TEXT,
                      dob TEXT,
                      role TEXT DEFAULT 'user',
                      email TEXT,
                      last_login TEXT)''')
        
        # Subjects table
        c.execute('''CREATE TABLE IF NOT EXISTS subjects
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT NOT NULL,
                      description TEXT)''')
        
        # Chapters table
        c.execute('''CREATE TABLE IF NOT EXISTS chapters
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      subject_id INTEGER NOT NULL,
                      name TEXT NOT NULL,
                      description TEXT,
                      FOREIGN KEY(subject_id) REFERENCES subjects(id))''')
        
        # Quizzes table
        c.execute('''CREATE TABLE IF NOT EXISTS quizzes
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      chapter_id INTEGER NOT NULL,
                      name TEXT NOT NULL,
                      description TEXT,
                      date_of_quiz TEXT,
                      time_duration TEXT,
                      is_active BOOLEAN DEFAULT 1,
                      FOREIGN KEY(chapter_id) REFERENCES chapters(id))''')
        
        # Questions table
        c.execute('''CREATE TABLE IF NOT EXISTS questions
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      quiz_id INTEGER NOT NULL,
                      question_statement TEXT NOT NULL,
                      option1 TEXT NOT NULL,
                      option2 TEXT NOT NULL,
                      option3 TEXT,
                      option4 TEXT,
                      correct_option INTEGER NOT NULL,
                      FOREIGN KEY(quiz_id) REFERENCES quizzes(id))''')
        
        # Scores table
        c.execute('''CREATE TABLE IF NOT EXISTS scores
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      quiz_id INTEGER NOT NULL,
                      user_id INTEGER NOT NULL,
                      time_stamp TEXT NOT NULL,
                      total_scored INTEGER NOT NULL,
                      total_questions INTEGER NOT NULL,
                      FOREIGN KEY(quiz_id) REFERENCES quizzes(id),
                      FOREIGN KEY(user_id) REFERENCES users(id))''')
        
        # Create admin user if doesn't exist
        c.execute("INSERT OR IGNORE INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)",
                  ('admin', 'admin123', 'Admin User', 'admin'))
        
        conn.commit()
        conn.close()

# Initialize database
init_db()

# Helper functions
def get_db_connection():
    return sqlite3.connect('quiz_master.db')

def get_current_user():
    return st.session_state.get('username')

def is_admin():
    if 'username' not in st.session_state:
        return False
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username=?", (st.session_state['username'],))
    result = c.fetchone()
    conn.close()
    return result and result[0] == 'admin'

def get_user_id(username):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (username,))
    user_id = c.fetchone()[0]
    conn.close()
    return user_id

def validate_login(username, password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT password, role FROM users WHERE username=?", (username,))
    result = c.fetchone()
    conn.close()
    
    if result and result[0] == password:
        return result[1]  # Return role
    return None

# Authentication
def login_page():
    st.title("Quiz Master - Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            role = validate_login(username, password)
            if role:
                st.session_state['username'] = username
                st.session_state['role'] = role
                st.session_state['page'] = 'dashboard'
                
                # Update last login
                conn = get_db_connection()
                conn.execute("UPDATE users SET last_login=? WHERE username=?", 
                           (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), username))
                conn.commit()
                conn.close()
                
                st.rerun()
            else:
                st.error("Invalid credentials")
    
    if st.button("Register New User"):
        st.session_state['page'] = 'register'
        st.rerun()

def register_page():
    st.title("Register New User")
    
    with st.form("register_form"):
        username = st.text_input("Username (email)")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        full_name = st.text_input("Full Name")
        email = st.text_input("Email")
        
        submitted = st.form_submit_button("Register")
        
        if submitted:
            if password != confirm_password:
                st.error("Passwords don't match!")
                return
                
            conn = get_db_connection()
            c = conn.cursor()
            
            try:
                c.execute("INSERT INTO users (username, password, full_name, email) VALUES (?, ?, ?, ?)",
                          (username, password, full_name, email))
                conn.commit()
                st.success("Registration successful! Please login.")
                st.session_state['page'] = 'login'
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Username already exists!")
            finally:
                conn.close()
    
    if st.button("Back to Login"):
        st.session_state['page'] = 'login'
        st.rerun()

# Admin Pages
def admin_dashboard():
    st.title("Admin Dashboard")
    
    menu = ["Subjects", "Chapters", "Quizzes", "Questions", "Users", "Reports"]
    choice = st.sidebar.selectbox("Menu", menu)
    
    if choice == "Subjects":
        manage_subjects()
    elif choice == "Chapters":
        manage_chapters()
    elif choice == "Quizzes":
        manage_quizzes()
    elif choice == "Questions":
        manage_questions()
    elif choice == "Users":
        manage_users()
    elif choice == "Reports":
        admin_reports()

def manage_subjects():
    st.header("Manage Subjects")
    conn = get_db_connection()
    
    # Add new subject
    with st.expander("Add New Subject"):
        with st.form("add_subject"):
            name = st.text_input("Subject Name*", help="Required field")
            description = st.text_area("Description")
            if st.form_submit_button("Add Subject"):
                if not name:
                    st.error("Subject name is required!")
                else:
                    conn.execute("INSERT INTO subjects (name, description) VALUES (?, ?)", 
                                (name.strip(), description.strip()))
                    conn.commit()
                    st.success("Subject added!")
                    st.rerun()
    
    # View and manage subjects
    st.subheader("All Subjects")
    subjects = pd.read_sql("SELECT * FROM subjects", conn)
    
    if not subjects.empty:
        st.dataframe(subjects)
        subject_id = st.selectbox("Select Subject", subjects['id'])
        
        col1, col2 = st.columns(2)
        with col1:
            with st.expander("Edit Subject"):
                subject = conn.execute("SELECT * FROM subjects WHERE id=?", (subject_id,)).fetchone()
                if subject:
                    with st.form("edit_subject"):
                        new_name = st.text_input("Name*", value=subject[1], help="Required field")
                        new_desc = st.text_area("Description", value=subject[2])
                        if st.form_submit_button("Update"):
                            if not new_name:
                                st.error("Subject name is required!")
                            else:
                                conn.execute("UPDATE subjects SET name=?, description=? WHERE id=?", 
                                            (new_name.strip(), new_desc.strip(), subject_id))
                                conn.commit()
                                st.success("Subject updated!")
                                st.rerun()
        
        with col2:
            with st.expander("Delete Subject"):
                if st.button("Delete Subject"):
                    if conn.execute("SELECT COUNT(*) FROM chapters WHERE subject_id=?", (subject_id,)).fetchone()[0] > 0:
                        st.error("Cannot delete - subject has chapters!")
                    else:
                        conn.execute("DELETE FROM subjects WHERE id=?", (subject_id,))
                        conn.commit()
                        st.success("Subject deleted!")
                        time.sleep(1)
                        st.rerun()
    else:
        st.info("No subjects found. Add your first subject above.")
    
    conn.close()

def manage_chapters():
    st.header("Manage Chapters")
    conn = get_db_connection()
    
    # Get all subjects for dropdown
    c = conn.cursor()
    c.execute("SELECT id, name FROM subjects")
    subjects = c.fetchall()
    subject_options = {id: name for id, name in subjects}
    
    if not subjects:
        st.warning("No subjects available. Please add subjects first.")
        conn.close()
        return
    
    # Add new chapter
    with st.expander("Add New Chapter"):
        with st.form("add_chapter"):
            subject_id = st.selectbox("Subject*", options=list(subject_options.keys()), 
                                     format_func=lambda x: subject_options[x],
                                     help="Required field")
            name = st.text_input("Chapter Name*", help="Required field")
            description = st.text_area("Description")
            if st.form_submit_button("Add Chapter"):
                if not name:
                    st.error("Chapter name is required!")
                else:
                    conn.execute("INSERT INTO chapters (subject_id, name, description) VALUES (?, ?, ?)", 
                                (subject_id, name.strip(), description.strip()))
                    conn.commit()
                    st.success("Chapter added!")
                    st.rerun()
    
    # View chapters by subject
    st.subheader("All Chapters")
    selected_subject = st.selectbox("Filter by Subject", options=list(subject_options.keys()), 
                                   format_func=lambda x: subject_options[x])
    
    chapters = pd.read_sql("SELECT c.id, s.name as subject, c.name, c.description FROM chapters c JOIN subjects s ON c.subject_id = s.id WHERE c.subject_id=?", 
                           conn, params=(selected_subject,))
    
    if not chapters.empty:
        st.dataframe(chapters)
        chapter_id = st.selectbox("Select Chapter", chapters['id'])
        
        col1, col2 = st.columns(2)
        with col1:
            with st.expander("Edit Chapter"):
                chapter = conn.execute("SELECT * FROM chapters WHERE id=?", (chapter_id,)).fetchone()
                if chapter:
                    with st.form("edit_chapter"):
                        new_subject = st.selectbox("Subject*", options=list(subject_options.keys()), 
                                                  format_func=lambda x: subject_options[x],
                                                  index=list(subject_options.keys()).index(chapter[1]),
                                                  help="Required field")
                        new_name = st.text_input("Name*", value=chapter[2], help="Required field")
                        new_desc = st.text_area("Description", value=chapter[3])
                        if st.form_submit_button("Update"):
                            if not new_name:
                                st.error("Chapter name is required!")
                            else:
                                conn.execute("UPDATE chapters SET subject_id=?, name=?, description=? WHERE id=?", 
                                            (new_subject, new_name.strip(), new_desc.strip(), chapter_id))
                                conn.commit()
                                st.success("Chapter updated!")
                                st.rerun()
        
        with col2:
            with st.expander("Delete Chapter"):
                if st.button("Delete Chapter"):
                    if conn.execute("SELECT COUNT(*) FROM quizzes WHERE chapter_id=?", (chapter_id,)).fetchone()[0] > 0:
                        st.error("Cannot delete - chapter has quizzes!")
                    else:
                        conn.execute("DELETE FROM chapters WHERE id=?", (chapter_id,))
                        conn.commit()
                        st.success("Chapter deleted!")
                        time.sleep(1)
                        st.rerun()
    else:
        st.info("No chapters found for selected subject.")
    
    conn.close()

def manage_quizzes():
    st.header("Manage Quizzes")
    conn = get_db_connection()
    
    # Get all chapters for dropdown
    c = conn.cursor()
    c.execute("SELECT c.id, s.name || ' - ' || c.name as chapter_name FROM chapters c JOIN subjects s ON c.subject_id = s.id")
    chapters = c.fetchall()
    chapter_options = {id: name for id, name in chapters}
    
    if not chapters:
        st.warning("No chapters available. Please add chapters first.")
        conn.close()
        return
    
    # Add new quiz
    with st.expander("Add New Quiz"):
        with st.form("add_quiz"):
            chapter_id = st.selectbox("Chapter*", options=list(chapter_options.keys()), 
                                     format_func=lambda x: chapter_options[x],
                                     help="Required field")
            name = st.text_input("Quiz Name*", help="Required field")
            description = st.text_area("Description")
            date_of_quiz = st.date_input("Quiz Date*", min_value=datetime.date.today(), help="Required field")
            time_duration = st.text_input("Duration (HH:MM)*", value="00:30", help="Format: HH:MM, Required")
            
            if st.form_submit_button("Add Quiz"):
                if not name or not time_duration or ':' not in time_duration:
                    st.error("Please fill all required fields with valid data!")
                else:
                    try:
                        # Validate time format
                        hours, minutes = map(int, time_duration.split(':'))
                        if hours < 0 or minutes < 0 or minutes >= 60:
                            raise ValueError
                            
                        conn.execute("INSERT INTO quizzes (chapter_id, name, description, date_of_quiz, time_duration) VALUES (?, ?, ?, ?, ?)", 
                                    (chapter_id, name.strip(), description.strip(), date_of_quiz.strftime('%Y-%m-%d'), time_duration))
                        conn.commit()
                        st.success("Quiz added!")
                        st.rerun()
                    except:
                        st.error("Invalid duration format! Use HH:MM")
    
    # View quizzes by chapter
    st.subheader("All Quizzes")
    selected_chapter = st.selectbox("Filter by Chapter", options=list(chapter_options.keys()), 
                                   format_func=lambda x: chapter_options[x])
    
    quizzes = pd.read_sql('''SELECT q.id, s.name as subject, c.name as chapter, q.name, q.description, 
                            q.date_of_quiz, q.time_duration, q.is_active
                            FROM quizzes q 
                            JOIN chapters c ON q.chapter_id = c.id 
                            JOIN subjects s ON c.subject_id = s.id 
                            WHERE q.chapter_id=?''', 
                          conn, params=(selected_chapter,))
    
    if not quizzes.empty:
        st.dataframe(quizzes)
        quiz_id = st.selectbox("Select Quiz", quizzes['id'])
        
        col1, col2 = st.columns(2)
        with col1:
            with st.expander("Edit Quiz"):
                quiz = conn.execute("SELECT * FROM quizzes WHERE id=?", (quiz_id,)).fetchone()
                if quiz:
                    with st.form("edit_quiz"):
                        new_chapter = st.selectbox("Chapter*", options=list(chapter_options.keys()), 
                                                  format_func=lambda x: chapter_options[x],
                                                  index=list(chapter_options.keys()).index(quiz[1]),
                                                  help="Required field")
                        new_name = st.text_input("Name*", value=quiz[2], help="Required field")
                        new_desc = st.text_area("Description", value=quiz[3])
                        new_date = st.date_input("Quiz Date*", 
                                               value=datetime.datetime.strptime(quiz[4], '%Y-%m-%d').date(),
                                               min_value=datetime.date.today(),
                                               help="Required field")
                        new_duration = st.text_input("Duration (HH:MM)*", value=quiz[5], help="Format: HH:MM, Required")
                        is_active = st.checkbox("Active", value=bool(quiz[6]))
                        
                        if st.form_submit_button("Update"):
                            if not new_name or not new_duration or ':' not in new_duration:
                                st.error("Please fill all required fields with valid data!")
                            else:
                                try:
                                    # Validate time format
                                    hours, minutes = map(int, new_duration.split(':'))
                                    if hours < 0 or minutes < 0 or minutes >= 60:
                                        raise ValueError
                                        
                                    conn.execute("UPDATE quizzes SET chapter_id=?, name=?, description=?, date_of_quiz=?, time_duration=?, is_active=? WHERE id=?", 
                                                (new_chapter, new_name.strip(), new_desc.strip(), 
                                                 new_date.strftime('%Y-%m-%d'), new_duration, 
                                                 int(is_active), quiz_id))
                                    conn.commit()
                                    st.success("Quiz updated!")
                                    st.rerun()
                                except:
                                    st.error("Invalid duration format! Use HH:MM")
        
        with col2:
            with st.expander("Delete Quiz"):
                if st.button("Delete Quiz"):
                    if conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz_id,)).fetchone()[0] > 0:
                        st.error("Cannot delete - quiz has questions!")
                    else:
                        conn.execute("DELETE FROM quizzes WHERE id=?", (quiz_id,))
                        conn.commit()
                        st.success("Quiz deleted!")
                        time.sleep(1)
                        st.rerun()
    else:
        st.info("No quizzes found for selected chapter.")
    
    conn.close()

def manage_questions():
    st.header("Manage Questions")
    conn = get_db_connection()
    
    # Get all quizzes for dropdown
    c = conn.cursor()
    c.execute('''SELECT q.id, s.name || ' - ' || c.name || ' - ' || q.name as quiz_name 
                 FROM quizzes q 
                 JOIN chapters c ON q.chapter_id = c.id 
                 JOIN subjects s ON c.subject_id = s.id
                 WHERE q.is_active = 1''')
    quizzes = c.fetchall()
    quiz_options = {id: name for id, name in quizzes}
    
    if not quizzes:
        st.warning("No active quizzes available. Please add quizzes first.")
        conn.close()
        return
    
    # Add new question
    with st.expander("Add New Question"):
        with st.form("add_question"):
            quiz_id = st.selectbox("Quiz*", options=list(quiz_options.keys()), 
                                  format_func=lambda x: quiz_options[x],
                                  help="Required field")
            question = st.text_area("Question Statement*", help="Required field")
            option1 = st.text_input("Option 1*", help="Required field")
            option2 = st.text_input("Option 2*", help="Required field")
            option3 = st.text_input("Option 3")
            option4 = st.text_input("Option 4")
            correct_option = st.radio("Correct Option*", [1, 2, 3, 4], index=0, horizontal=True,
                                    help="Required - select which option is correct")
            
            if st.form_submit_button("Add Question"):
                if not question or not option1 or not option2:
                    st.error("Please fill all required fields!")
                else:
                    conn.execute('''INSERT INTO questions 
                                (quiz_id, question_statement, option1, option2, option3, option4, correct_option) 
                                VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                              (quiz_id, question.strip(), option1.strip(), option2.strip(), 
                               option3.strip() if option3 else None, 
                               option4.strip() if option4 else None, 
                               correct_option))
                    conn.commit()
                    st.success("Question added!")
                    st.rerun()
    
    # View questions by quiz
    st.subheader("All Questions")
    selected_quiz = st.selectbox("Filter by Quiz", options=list(quiz_options.keys()), 
                                format_func=lambda x: quiz_options[x])
    
    questions = pd.read_sql('''SELECT id, question_statement, option1, option2, 
                             option3, option4, correct_option 
                             FROM questions WHERE quiz_id=?''', 
                           conn, params=(selected_quiz,))
    
    if not questions.empty:
        st.dataframe(questions)
        question_id = st.selectbox("Select Question", questions['id'])
        
        col1, col2 = st.columns(2)
        with col1:
            with st.expander("Edit Question"):
                question = conn.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
                if question:
                    with st.form("edit_question"):
                        new_quiz = st.selectbox("Quiz*", options=list(quiz_options.keys()), 
                                              format_func=lambda x: quiz_options[x],
                                              index=list(quiz_options.keys()).index(question[1]),
                                              help="Required field")
                        new_question = st.text_area("Question*", value=question[2], help="Required field")
                        new_option1 = st.text_input("Option 1*", value=question[3], help="Required field")
                        new_option2 = st.text_input("Option 2*", value=question[4], help="Required field")
                        new_option3 = st.text_input("Option 3", value=question[5] if question[5] else "")
                        new_option4 = st.text_input("Option 4", value=question[6] if question[6] else "")
                        new_correct = st.radio("Correct Option*", [1, 2, 3, 4], 
                                             index=question[7]-1, horizontal=True,
                                             help="Required - select which option is correct")
                        
                        if st.form_submit_button("Update"):
                            if not new_question or not new_option1 or not new_option2:
                                st.error("Please fill all required fields!")
                            else:
                                conn.execute('''UPDATE questions SET 
                                            quiz_id=?, question_statement=?, option1=?, option2=?, option3=?, option4=?, correct_option=?
                                            WHERE id=?''', 
                                          (new_quiz, new_question.strip(), new_option1.strip(), new_option2.strip(), 
                                           new_option3.strip() if new_option3 else None, 
                                           new_option4.strip() if new_option4 else None, 
                                           new_correct, question_id))
                                conn.commit()
                                st.success("Question updated!")
                                st.rerun()
        
        with col2:
            with st.expander("Delete Question"):
                if st.button("Delete Question"):
                    conn.execute("DELETE FROM questions WHERE id=?", (question_id,))
                    conn.commit()
                    st.success("Question deleted!")
                    time.sleep(1)
                    st.rerun()
    else:
        st.info("No questions found for selected quiz.")
    
    conn.close()

def manage_users():
    st.header("Manage Users")
    conn = get_db_connection()
    
    # View all users
    st.subheader("All Users")
    users = pd.read_sql("SELECT id, username, full_name, qualification, dob, role FROM users", conn)
    
    if not users.empty:
        st.dataframe(users)
        user_id = st.selectbox("Select User", users['id'])
        
        col1, col2 = st.columns(2)
        with col1:
            with st.expander("Edit User"):
                user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                if user:
                    with st.form("edit_user"):
                        st.write(f"Username: {user[1]}")
                        new_fullname = st.text_input("Full Name", value=user[3])
                        new_qual = st.text_input("Qualification", value=user[4])
                        new_dob = st.date_input("Date of Birth", 
                                               value=datetime.datetime.strptime(user[5], '%Y-%m-%d').date() if user[5] else datetime.date.today())
                        new_email = st.text_input("Email", value=user[7] if user[7] else "")
                        new_role = st.selectbox("Role", ['user', 'admin'], 
                                              index=0 if user[6] == 'user' else 1)
                        
                        if st.form_submit_button("Update"):
                            conn.execute('''UPDATE users SET 
                                        full_name=?, qualification=?, dob=?, email=?, role=?
                                        WHERE id=?''', 
                                      (new_fullname.strip(), new_qual.strip(), 
                                       new_dob.strftime('%Y-%m-%d'), new_email.strip(), 
                                       new_role, user_id))
                            conn.commit()
                            st.success("User updated!")
                            st.rerun()
        
        with col2:
            with st.expander("Delete User"):
                if st.button("Delete User"):
                    # Check if user is admin
                    role = conn.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()[0]
                    
                    if role == 'admin':
                        st.error("Cannot delete admin user!")
                    else:
                        # Check if user has quiz attempts
                        if conn.execute("SELECT COUNT(*) FROM scores WHERE user_id=?", (user_id,)).fetchone()[0] > 0:
                            st.error("Cannot delete - user has quiz attempts!")
                        else:
                            conn.execute("DELETE FROM users WHERE id=?", (user_id,))
                            conn.commit()
                            st.success("User deleted!")
                            time.sleep(1)
                            st.rerun()
    else:
        st.info("No users found.")
    
    conn.close()

def admin_reports():
    st.header("Admin Reports")
    conn = get_db_connection()
    
    # Quiz statistics
    st.subheader("Quiz Statistics")
    quiz_stats = pd.read_sql('''SELECT q.name as quiz, COUNT(s.id) as attempts, 
                               AVG(s.total_scored*100.0/s.total_questions) as avg_score,
                               MAX(s.total_scored*100.0/s.total_questions) as high_score,
                               MIN(s.total_scored*100.0/s.total_questions) as low_score
                               FROM scores s
                               JOIN quizzes q ON s.quiz_id = q.id
                               GROUP BY q.id, q.name''', conn)
    
    if not quiz_stats.empty:
        st.dataframe(quiz_stats)
        
        # Display chart
        fig = px.bar(quiz_stats, x='quiz', y='avg_score', 
                     title='Average Scores by Quiz',
                     labels={'quiz': 'Quiz Name', 'avg_score': 'Average Score (%)'})
        st.plotly_chart(fig)
    else:
        st.warning("No quiz attempts yet.")
    
    # User statistics
    st.subheader("User Statistics")
    user_stats = pd.read_sql('''SELECT u.username, u.full_name, 
                               COUNT(s.id) as attempts, 
                               AVG(s.total_scored*100.0/s.total_questions) as avg_score,
                               MAX(s.total_scored*100.0/s.total_questions) as high_score,
                               MIN(s.total_scored*100.0/s.total_questions) as low_score
                               FROM scores s
                               JOIN users u ON s.user_id = u.id
                               GROUP BY u.id, u.username, u.full_name''', conn)
    
    if not user_stats.empty:
        st.dataframe(user_stats)
        
        # Display chart
        fig = px.bar(user_stats, x='username', y='avg_score', 
                     title='Average Scores by User',
                     labels={'username': 'Username', 'avg_score': 'Average Score (%)'})
        st.plotly_chart(fig)
    else:
        st.warning("No user attempts yet.")
    
    # Export options
    st.subheader("Export Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        quiz_results = pd.read_sql('''SELECT q.name as quiz, u.username, 
                                     s.total_scored, s.total_questions, 
                                     (s.total_scored*100.0/s.total_questions) as percentage,
                                     s.time_stamp
                                     FROM scores s
                                     JOIN quizzes q ON s.quiz_id = q.id
                                     JOIN users u ON s.user_id = u.id''', conn)
        
        if not quiz_results.empty:
            csv = quiz_results.to_csv(index=False)
            st.download_button(
                label="Download Quiz Results CSV",
                data=csv,
                file_name='quiz_results.csv',
                mime='text/csv'
            )
        else:
            st.warning("No quiz results to export")
    
    with col2:
        user_stats = pd.read_sql('''SELECT u.username, u.full_name, 
                                   COUNT(s.id) as attempts, 
                                   AVG(s.total_scored*100.0/s.total_questions) as avg_score,
                                   MAX(s.total_scored*100.0/s.total_questions) as high_score,
                                   MIN(s.total_scored*100.0/s.total_questions) as low_score
                                   FROM scores s
                                   JOIN users u ON s.user_id = u.id
                                   GROUP BY u.id, u.username, u.full_name''', conn)
        
        if not user_stats.empty:
            csv = user_stats.to_csv(index=False)
            st.download_button(
                label="Download User Stats CSV",
                data=csv,
                file_name='user_stats.csv',
                mime='text/csv'
            )
        else:
            st.warning("No user stats to export")
    
    conn.close()

# User Pages
def user_dashboard():
    st.title("User Dashboard")
    
    menu = ["Available Quizzes", "Take Quiz", "My Scores", "Profile"]
    choice = st.sidebar.selectbox("Menu", menu)
    
    if choice == "Available Quizzes":
        available_quizzes()
    elif choice == "Take Quiz":
        take_quiz()
    elif choice == "My Scores":
        my_scores()
    elif choice == "Profile":
        user_profile()

def available_quizzes():
    st.header("Available Quizzes")
    conn = get_db_connection()
    
    # Get all active quizzes
    quizzes = pd.read_sql('''SELECT q.id, s.name as subject, c.name as chapter, q.name as quiz, 
                            q.description, q.date_of_quiz, q.time_duration
                            FROM quizzes q
                            JOIN chapters c ON q.chapter_id = c.id
                            JOIN subjects s ON c.subject_id = s.id
                            WHERE q.is_active = 1
                            ORDER BY q.date_of_quiz''', conn)
    
    if not quizzes.empty:
        st.dataframe(quizzes)
    else:
        st.info("No quizzes available at the moment. Please check back later.")
    
    conn.close()

def take_quiz():
    st.header("Take Quiz")
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get all active quizzes
    c.execute('''SELECT q.id, s.name || ' - ' || c.name || ' - ' || q.name as quiz_name
                 FROM quizzes q
                 JOIN chapters c ON q.chapter_id = c.id
                 JOIN subjects s ON c.subject_id = s.id
                 WHERE q.is_active = 1''')
    quizzes = c.fetchall()
    quiz_options = {id: name for id, name in quizzes}
    
    if not quizzes:
        st.warning("No quizzes available at the moment.")
        conn.close()
        return
    
    selected_quiz = st.selectbox("Select Quiz", options=list(quiz_options.keys()), 
                                format_func=lambda x: quiz_options[x])
    
    # Check if user has already taken this quiz
    user_id = get_user_id(get_current_user())
    c.execute("SELECT COUNT(*) FROM scores WHERE quiz_id=? AND user_id=?", (selected_quiz, user_id))
    already_taken = c.fetchone()[0] > 0
    
    if already_taken:
        st.warning("You have already taken this quiz.")
        conn.close()
        return
    
    # Get quiz duration
    c.execute("SELECT time_duration FROM quizzes WHERE id=?", (selected_quiz,))
    duration = c.fetchone()[0]
    hours, minutes = map(int, duration.split(':'))
    total_seconds = hours * 3600 + minutes * 60
    
    # Get questions for the quiz
    c.execute("SELECT id, question_statement, option1, option2, option3, option4, correct_option FROM questions WHERE quiz_id=?", (selected_quiz,))
    questions = c.fetchall()
    
    if not questions:
        st.warning("This quiz has no questions yet.")
        conn.close()
        return
    
    # Quiz form
    with st.form("quiz_form"):
        answers = {}
        st.warning(f"Time limit: {duration} (HH:MM)")
        
        for i, (q_id, question, opt1, opt2, opt3, opt4, correct_opt) in enumerate(questions, 1):
            st.subheader(f"Question {i}")
            st.write(question)
            
            options = [opt1, opt2]
            if opt3: options.append(opt3)
            if opt4: options.append(opt4)
            
            answers[q_id] = st.radio(f"Select your answer:", options, key=f"q_{q_id}")
        
        submitted = st.form_submit_button("Submit Quiz")
        
        if submitted:
            # Calculate score
            score = 0
            for q_id, user_answer in answers.items():
                c.execute("SELECT correct_option FROM questions WHERE id=?", (q_id,))
                correct_opt = c.fetchone()[0]
                
                # Find which option number the user selected
                c.execute("SELECT option1, option2, option3, option4 FROM questions WHERE id=?", (q_id,))
                options = c.fetchone()
                
                selected_option = None
                for i, opt in enumerate(options, 1):
                    if opt and opt == user_answer:
                        selected_option = i
                        break
                
                if selected_option == correct_opt:
                    score += 1
            
            # Save score
            total_questions = len(questions)
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            c.execute("INSERT INTO scores (quiz_id, user_id, time_stamp, total_scored, total_questions) VALUES (?, ?, ?, ?, ?)",
                      (selected_quiz, user_id, timestamp, score, total_questions))
            conn.commit()
            
            st.success(f"Quiz submitted! Your score: {score}/{total_questions} ({(score/total_questions)*100:.1f}%)")
            time.sleep(2)
            st.rerun()
    
    conn.close()

def my_scores():
    st.header("My Quiz Scores")
    user_id = get_user_id(get_current_user())
    conn = get_db_connection()
    
    # Get all scores for the user
    scores = pd.read_sql('''SELECT q.name as quiz, s.total_scored, s.total_questions, 
                           (s.total_scored*100.0/s.total_questions) as percentage,
                           s.time_stamp
                           FROM scores s
                           JOIN quizzes q ON s.quiz_id = q.id
                           WHERE s.user_id=?
                           ORDER BY s.time_stamp DESC''', conn, params=(user_id,))
    
    if not scores.empty:
        st.dataframe(scores)
        
        # Display chart
        fig = px.bar(scores, x='quiz', y='percentage', 
                     title='Your Quiz Performance',
                     labels={'quiz': 'Quiz Name', 'percentage': 'Score (%)'})
        st.plotly_chart(fig)
        
        # Calculate stats
        avg_score = scores['percentage'].mean()
        best_score = scores['percentage'].max()
        total_attempts = len(scores)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Average Score", f"{avg_score:.1f}%")
        col2.metric("Best Score", f"{best_score:.1f}%")
        col3.metric("Total Attempts", total_attempts)
    else:
        st.info("You haven't taken any quizzes yet.")
    
    conn.close()

def user_profile():
    st.header("My Profile")
    username = get_current_user()
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    user = c.fetchone()
    
    if user:
        st.write(f"**Username:** {user[1]}")
        st.write(f"**Full Name:** {user[3]}")
        st.write(f"**Qualification:** {user[4]}")
        st.write(f"**Date of Birth:** {user[5]}")
        st.write(f"**Email:** {user[7]}")
        
        # Update profile
        with st.expander("Update Profile"):
            with st.form("update_profile"):
                new_fullname = st.text_input("Full Name", value=user[3])
                new_qual = st.text_input("Qualification", value=user[4])
                new_dob = st.date_input("Date of Birth", 
                                       value=datetime.datetime.strptime(user[5], '%Y-%m-%d').date() if user[5] else datetime.date.today())
                new_email = st.text_input("Email", value=user[7] if user[7] else "")
                new_password = st.text_input("New Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                
                if st.form_submit_button("Update Profile"):
                    if new_password and new_password != confirm_password:
                        st.error("Passwords don't match!")
                    else:
                        update_query = '''UPDATE users SET 
                                        full_name=?, qualification=?, dob=?, email=?'''
                        params = [new_fullname.strip(), new_qual.strip(), 
                                 new_dob.strftime('%Y-%m-%d'), new_email.strip()]
                        
                        if new_password:
                            update_query += ', password=?'
                            params.append(new_password)
                        
                        update_query += ' WHERE username=?'
                        params.append(username)
                        
                        c.execute(update_query, tuple(params))
                        conn.commit()
                        st.success("Profile updated!")
                        time.sleep(1)
                        st.rerun()
    
    conn.close()

# Dashboard
def dashboard():
    st.title(f"Welcome to Quiz Master, {get_current_user()}!")
    
    if is_admin():
        st.success("You are logged in as an Administrator")
        if st.button("Go to Admin Dashboard"):
            st.session_state['page'] = 'admin_dashboard'
            st.rerun()
    else:
        st.info("You are logged in as a Regular User")
        if st.button("Go to User Dashboard"):
            st.session_state['page'] = 'user_dashboard'
            st.rerun()
    
    if st.button("Logout"):
        st.session_state.clear()
        st.session_state['page'] = 'login'
        st.rerun()

# Main App
def main():
    st.set_page_config(page_title="Quiz Master", layout="wide")
    
    if 'page' not in st.session_state:
        st.session_state['page'] = 'login'
    
    if st.session_state['page'] == 'login':
        login_page()
    elif st.session_state['page'] == 'register':
        register_page()
    elif st.session_state['page'] == 'dashboard':
        dashboard()
    elif st.session_state['page'] == 'admin_dashboard':
        admin_dashboard()
    elif st.session_state['page'] == 'user_dashboard':
        user_dashboard()

if __name__ == "__main__":
    main()