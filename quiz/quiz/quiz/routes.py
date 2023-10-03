from quiz import app,db, socketio
from quiz.models import Class,Quiz,Option, Question, LiveQuiz, QuizLog, User, QuizAttempts
from quiz.forms import AddQuizForm, AddLiveQuizForm
from flask_login import  current_user, login_required
from quiz.utils import quizcode_generator , live_quizcode_generator
from flask import render_template, redirect, url_for, request, flash, session
from flask_socketio import emit
from random import shuffle
from datetime import datetime, timedelta

student_details = []
current_running = []

@app.route('/classinfo/Add_Quiz', methods=['GET', 'POST'])
@login_required
def add_quiz():
    user_classes = Class.query.filter_by(creator_id=current_user.id).all()

    form = AddQuizForm()
    form.class_id.choices = [(class_.id, class_.class_name) for class_ in user_classes]
    quiz_code = quizcode_generator()
    if request.method == 'POST' and form.validate_on_submit():
        num_questions = form.num_questions.data  # Get the number of questions from the form

        quiz = Quiz(
            class_id=form.class_id.data,
            quiz_code=quiz_code,
            title=form.title.data,
            timer=form.timer.data
        )
        db.session.add(quiz)
        db.session.commit()

        for i in range(num_questions):
            question_text = request.form.get(f'question_{i + 1}')  
            if question_text:
                question = Question(quiz_id=quiz.id, text=question_text)
                db.session.add(question)
                db.session.commit()

                options = []
                for j in range(1, 5):
                    option_text = request.form.get(f'question_{i + 1}_option_{j}')
                    if option_text:
                        options.append(option_text)

                if len(options) == 4:
                    option = Option(
                        question_id=question.id,
                        quiz_id=quiz.id,
                        option1=options[0],
                        option2=options[1],
                        option3=options[2],
                        option4=options[3]
                    )
                    db.session.add(option)
                    db.session.commit()

        flash('Quiz has been added', 'success')
        return redirect(url_for('class_info', classid=form.class_id.data))

    return render_template('addquiz.html', form=form, user_classes=user_classes)

@app.route('/quiz/<int:quiz_id>')
def quiz_details(quiz_id):
    quiz =Quiz.query.get_or_404(quiz_id)
    total_questions = len(quiz.questions)
    return render_template('quizdetails.html',quiz=quiz, current_user=current_user, total_questions=total_questions)

@app.route('/delete/<int:quiz_id>')
def delete_quiz(quiz_id): 
    quiz = Quiz.query.get_or_404(quiz_id)
    classid = quiz.class_id 
    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    for question in questions:
        options = Option.query.filter_by(question_id=question.id).all()
        for option in options:
            db.session.delete(option)
        db.session.delete(question)
    db.session.delete(quiz)
    db.session.commit()
    flash('Quiz has been Deleted', 'success')
    return redirect(url_for('class_info', classid=classid))


@app.route('/submit_quiz/<int:quiz_id>', methods=['POST'])
def submit_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    score = 0
    for question in quiz.questions:
        selected_option_id = int(request.form.get(f'question_{question.id}'))
        selected_option = Option.query.get(selected_option_id)
        if selected_option.is_correct:
            score += 1

    # Save the score in the database or take any other necessary actions

    return redirect(url_for('quiz_result', quiz_id=quiz.id, score=score))


@app.route('/livequiz', methods=['POST','GET'])
def add_livequiz(): 
    class_id = request.form.get('class_id')
    form = AddLiveQuizForm()
    quiz_code = live_quizcode_generator()
    user_classes = Class.query.filter_by(creator_id=current_user.id).all()
    if request.method == 'POST' and form.validate_on_submit():
        num_questions = form.num_questions.data  
        
        if class_id:
            quiz = Quiz(
                quiz_code=quiz_code,
                class_id= class_id,
                title=form.title.data,
                timer=form.timer.data
            )
        else:
            quiz = Quiz(
                quiz_code=quiz_code,
                title=form.title.data,
                timer=form.timer.data
            )
        session['livequiztitle'] = form.title.data
        db.session.add(quiz)
        db.session.commit()
        for i in range(num_questions):
            question_text = request.form.get(f'question_{i + 1}')  
            if question_text:
                question = Question(quiz_id=quiz.id, text=question_text)
                db.session.add(question)
                db.session.commit()
                options = []
                for j in range(1, 5):
                    option_text = request.form.get(f'question_{i + 1}_option_{j}')
                    if option_text:
                        options.append(option_text)
                if len(options) == 4:
                    option = Option(
                        question_id=question.id,
                        quiz_id=quiz.id,
                        option1=options[0],
                        option2=options[1],
                        option3=options[2],
                        option4=options[3]
                    )
                    db.session.add(option)
                    db.session.commit()
        livequiz = LiveQuiz(quiz_id=quiz.id, quiz_code=quiz_code,creator_id=current_user.id, datetime=datetime.now())       
        db.session.add(livequiz)
        db.session.commit()
        session['quiz_id'] = quiz.id
        
        return render_template('startorlater.html',quiz_id=quiz.id)
    return render_template('addLivequiz.html', form=form,user_classes=user_classes )

@app.route('/start_live_quiz/<int:quiz_id>', methods=['GET','POST'])
def start_live_quiz(quiz_id):
    livequiz = LiveQuiz.query.get_or_404(quiz_id)
    quiz = Quiz.query.get_or_404(quiz_id)
    if current_user.id == livequiz.creator_id: 
        current_running.append(quiz)
    students_in_quiz = [student for student in student_details if student['quiz_id'] == quiz_id]
    image_file = url_for('static', filename='profiles/' + 'participant.png')
    participants = len(students_in_quiz)
    
    return render_template('startlivequiz.html',image_file=image_file,livequiz=livequiz,quiztitle=quiz.title,students_in_quiz=students_in_quiz, participants=participants, current_user=current_user)

@app.route('/JoinQuiz/<int:quiz_code>', methods=['POST', 'GET'])
def join_quiz(quiz_code):
    print("==============",quiz_code)
    username = session['current_user']['username']
    print("================vwsdwsin",username)
    quiz = Quiz.query.filter_by(quiz_code=quiz_code).first()
    print(quiz)
    if quiz:
        student_details.append({'quiz_id': quiz.id, 'username':username})
        attempts = QuizAttempts(quiz_id=quiz.id,student_id=session['current_user']['id'],quiz_code=quiz_code)
        db.session.add(attempts)
        db.session.commit() 
        socketio.emit('join_quiz', {'username': username, 'quiz_id': quiz.id}, room=quiz.id)
        return redirect(url_for('start_live_quiz',quiz_id=quiz.id))
    else: 
        flash("No Quiz Found","info")
        return redirect(url_for('home'))
    
@socketio.on('join_quiz')
def handle_join_quiz(data):
    username = data['username']
    quiz_id = data['quiz_id']

    # Store student details
    student_details.append({'quiz_id': quiz_id, 'username': username})

    # Emit an event to notify all clients about the new student joining
    emit('join_quiz', {'username': username, 'quiz_id': quiz_id}, broadcast=True)

@app.route('/exit_quiz')
def exit_quiz(): 
    return redirect(url_for('home'))

@app.route('/quiz/start-<int:quiz_id>')
def start_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = Quiz.questions
    print(questions)


@app.route('/running_quiz/<int:quiz_code>', methods=['GET','POST'])
def running_quiz(quiz_code):
    # quiz = Quiz.query.get(quiz_code)
    emit('quiz_started', {'quiz_code': quiz_code}, namespace='/quiz')
    quiz = Quiz.query.filter_by(quiz_code=quiz_code).first()

    # Check if the quiz exists
    if quiz is None:
        return "Invalid quiz code"
    question = quiz.questions
    import random

    # Convert questions to a list
    questions = list(question)
    # Shuffle the questions randomly and select a subset
    random.shuffle(questions)
    print(questions)
    # Initialize the session variables for storing the current question index and the score
    if 'current_question' not in session:
        session['current_question'] = 0
    if 'score' not in session:
        session['score'] = 0
    
    # Check if the user has submitted an answer
    if request.method == 'POST':
        # Get the user's answer from the form
        answer = request.form.get('answer')
        # Get the correct answer from the database
        correct_answer = questions[session['current_question']].options[0].option4 # Assuming option1 is always correct
        # Compare the user's answer with the correct answer and update the score accordingly
        if answer == correct_answer:
            session['score'] += 1
        
        # Increment the current question index by 1	
        session['current_question'] += 1
    
    # Check if there are more questions left
    if session['current_question'] < len(questions):
        # Get the current question object
        question = questions[session['current_question']]
        # Get the options for the current question
        if question.options:
            options = question.options[0]
        else:
             options = None
        
        # Render the quiz template with the quiz, question, and options data
        return render_template('question_template.html', quiz=quiz, question=question, options=options, timer=quiz.timer)
    
    else:
        result = session['score']
        # Reset the session variables
        session.pop('current_question')
        session.pop('score')
        # Render a message to indicate that the quiz is over
        quizlog = QuizLog(quiz_id=quiz.id,student_id=current_user.id,entered_answer=answer, correct_answer=correct_answer, total_marks=result)
        db.session.add(quizlog)
        db.session.commit()
        return render_template("quizresult.html",result=result)


# @app.route('/quiz_result/<int:quiz_id>/<int:score>')
# def quiz_result(quiz_id, score):
#     quiz = Quiz.query.get_or_404(quiz_id)
#     return render_template('quizresult.html', quiz=quiz, score=score)

@app.route('/quiz/<int:quiz_id>/results')
def quiz_result(quiz_id): 
    return ''