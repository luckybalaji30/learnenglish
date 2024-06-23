
from flask import Flask, render_template, request,url_for, redirect,session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user,login_required
from datetime import datetime
import numpy as np
import copy
import os, time
from flask import flash, redirect, url_for,g
from werkzeug.utils import secure_filename
import pandas as pd

app = Flask(__name__)

# initialise SQlLite 
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite"
app.config["SECRET_KEY"] = "pranava"
db = SQLAlchemy()

#kick off with Login Manager initialization
login_manager = LoginManager()
login_manager.init_app(app)

#define structure of the User details
class Users(UserMixin, db.Model):
	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(250), unique=True, nullable=False)
	password = db.Column(db.String(250), nullable=False)
	lastlogin = db.Column(db.DateTime, nullable=False)

#Initiate app ( Create db file for the 1st time)
db.init_app(app)

with app.app_context():
	db.create_all()

#flask login module initiate comm with flask requests
@login_manager.user_loader
def loader_user(user_id):
	return Users.query.get(user_id)

# global variables
CURRENT_FOLDER= os.getcwd()
WORDS_FOLDER_ROOT= os.path.join(CURRENT_FOLDER,"Wordsbank")
USERS_WORD_FOLDER=""
UPLOAD_FOLDER = '/Users/balajis/Balaji/Learning/Python/pranav01/'
ALLOWED_EXTENSIONS = {'csv'}
filename="pranavawordlist.csv"
WORDS_BANK_FILE_NAME="wordsbank.csv"

#fullfilename=os.path.join(UPLOAD_FOLDER,WORDS_BANK_FILE_NAME)
#data = pd.read_csv(fullfilename)
original_englishwords={}
englishwords={}
words=[]
spell_word_list=[]
meanings=[]


no_of_choices=4
no_of_questions=10
#original_englishwords = dict(zip(data.Word, data.Meaning))
#englishwords = copy.deepcopy(original_englishwords)
#words=[i for i in englishwords.keys()]
#meanings=[i for i in englishwords.values()]
    

def refresh_word(username):
    global words, meanings, englishwords, original_englishwords,spell_word_list,USERS_WORD_FOLDER
    
    #Derive word bank from the user name
    
    USERS_WORD_FOLDER=os.path.join(WORDS_FOLDER_ROOT,username)
    wordsbankfile= os.path.join(USERS_WORD_FOLDER, WORDS_BANK_FILE_NAME)

    # get count of previous word bank if it has
    prev_cnt=len(words)

    print ("(Refresh_word)Username:", username, "wordsbankfile:",wordsbankfile)
    # refreshing word bank variables
    data = pd.read_csv(wordsbankfile)
    original_englishwords = dict(zip(data.Word, data.Meaning))
    englishwords = copy.deepcopy(original_englishwords)

    # Store in the word and it's meanings
    words=[i for i in englishwords.keys()]
    meanings=[i for i in englishwords.values()]
    cur_cnt=len(words)
    spell_word_list=[ii for ii in words if not ' ' in ii]
    return prev_cnt, cur_cnt


def construct_options(existingWordList):
    
    while True:
        curWordIndex=np.random.choice(len(words)-1,1)[0]
        if words[curWordIndex] not in existingWordList:
            break
    curWordMeaning=englishwords[words[curWordIndex]]
    #print("curwordindex <", curWordIndex,  "> word <",words[curWordIndex]," > curword <",curWordMeaning,">")
    curChoices=[curWordMeaning]
    while len(curChoices) < no_of_choices:
        ch = np.random.choice(range(1,len(meanings),1))
        while ch == curWordIndex or meanings[ch] in curChoices:
            ch = np.random.choice(range(1,len(meanings),1))
        curChoices.append(meanings[ch])
    return words[curWordIndex], curChoices

# Check existence of folder and read the file from the folder
def init_word_cache(user):
    global USERS_WORD_FOLDER
    print ("(init_word_cache)Username", user.username)
    USERS_WORD_FOLDER=os.path.join(WORDS_FOLDER_ROOT,user.username)

    # Folder setup
    if not os.path.exists(USERS_WORD_FOLDER):
        print(" Folder doesn't exists, creating it")
        os.makedirs(USERS_WORD_FOLDER)
    else:
        print(" Folder exists") 

    # Read the last latest file from the current folder
    wordsbankfile= os.path.join(USERS_WORD_FOLDER, WORDS_BANK_FILE_NAME)
    if not os.path.exists(wordsbankfile):
        return "Words Bank file is required to be upload before using this."
    
     # Get the file modification time (Unix timestamp)
    modification_time = os.path.getmtime(wordsbankfile)
    modification_time_readable = time.ctime(modification_time)

    p_cnt, c_cnt =  refresh_word(user.username)
    print ( "p_cnt:", p_cnt, "c_cnt:", c_cnt)

    with open(wordsbankfile, 'r') as file:
        line_count = sum(1 for line in file)

    msg="Using file uploaded on "+modification_time_readable + " having " + str(line_count) + " for practice"
    return msg
        
# Landing page to access this application
@app.route("/")
def home():
	return render_template("landingpage.html")

# register for new user
@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            user = Users(username=request.form.get("username"),
            password=request.form.get("password"),
            lastlogin = datetime.now())
            db.session.add(user)
            db.session.commit() 
            return redirect(url_for("login"))
        except Exception as e:
           print ("<Caugth Exception>",e)
           msg="User already exists, please retry" 
           return render_template("login_with_error.html", err=msg)
    return render_template("sign_up.html")

# After receiving login credetials
@app.route("/login", methods=["GET", "POST"])
def login():
    try:
        if request.method == "POST":
            user = Users.query.filter_by(
            username=request.form.get("username")).first()
            if user is None:
                msg="User doesn't exists, please"
                render_template("login_with_error.html", err=msg)
            if user.password == request.form.get("password"):
                login_user(user)
                session['username'] = user.username
                msg=init_word_cache(user)
                return render_template("index.html", msg=msg)
        return render_template("login.html")
    
    except AttributeError as e:
        print ("<Caugth Exception>",e)
        msg="User doesn't exists, please "
    return render_template("login_with_error.html", err=msg)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

# On successful login access this page
@app.route('/mainpage')
@login_required
def index():
    # retrieve username from the session
    username  = session["username"]
    p,c = refresh_word(username)
    return render_template('index.html')

@app.route('/upload')
@login_required
def upload():
    return render_template('upload.html')

@app.route('/refresh')
@login_required
def refresh():

    if len(words) == 0:
        return render_template("index.html", msg="Words Bank file is required to be upload before using this.")

    # retrieve username from the session
    username  = session["username"]
    p,c= refresh_word(username)
    return render_template('data_refreshed.html',
                                    p=p, c=c)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/uploadsubmit', methods=['GET', 'POST'])
@login_required
def upload_file():
    # retrieve username from the session
    username  = session["username"]

    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        

        
        print( "USERS_WORD_FOLDER:", USERS_WORD_FOLDER, "filename:",file.filename, "WORDS_FOLDER_ROOT:",WORDS_FOLDER_ROOT)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            f_filename = os.path.join(USERS_WORD_FOLDER,filename)

            # Preserver the previous version of the file
            if os.path.exists(f_filename):
                # Get the create time of the file
                create_time = os.path.getctime( f_filename )
                
                # get the readable timestamp format 
                format_time = datetime.fromtimestamp( create_time )
                
                #convert time into string
                format_time_string = format_time.strftime("%Y_%m_%d_%H_%M_%S") # e.g. 2015_01_01_09_00_00
                
                #consruct the new name of the file
                oldfile = f_filename + format_time_string 

                if os.path.exists(f_filename):
                    os.rename(f_filename,oldfile)
                
            file.save(os.path.join(USERS_WORD_FOLDER,f_filename))

            p_cnt, c_cnt =  refresh_word(username)
            print ( "p_cnt:", p_cnt, "c_cnt:", c_cnt)

            return render_template('uploaded_file.html',
                                    filename=filename)
    return

@app.route('/quiz')
def quiz():
    cur_question_no=0
    questionWordList=[]
    global questions_shuffles
    questions_shuffles={}
    if len(words) == 0:
        return render_template("index.html", msg="Words Bank file is required to be upload before using this.")
        

    while cur_question_no < no_of_questions:
        word, options=construct_options(questionWordList)
        questionWordList.extend([word])
        np.random.shuffle(options)
        cur_question_no+= 1
        questions_shuffles[word]=options
    
    return render_template('quiz.html', q = questions_shuffles)

@app.route('/quiz_answer', methods=['POST'])
def quiz_answers():
    correct = 0
    correct_answer={} 
    correct_answer_display={}
    
    # Loop thru answer key to validate answers received from form
    # iterates thru word
    for i in questions_shuffles.keys():
        answered = request.form[i]
        print("i <",i, "> answered <",answered, "> value <",original_englishwords[i],">" )
        
        correct_answer[i]=original_englishwords[i] 
        if original_englishwords[i] == answered:
            correct = correct+1
            correct_answer_display[i]=True
        else:
            correct_answer_display[i]=False
    return render_template('quiz_answer.html', count=correct,ca=correct_answer,cad=correct_answer_display)


@app.route('/spell')
def spell():
 
    global spelling_test_word
    spelling_test_word={}

    if len(words) == 0:
        return render_template("index.html", msg="Words Bank file is required to be upload before using this.")
        
    cur_word_list = np.random.choice(spell_word_list,10, replace=False)
    
    print("cur_word_list",cur_word_list)
    for i in range(len(cur_word_list)):
        cur_word=cur_word_list[i]
        word_len=len(cur_word_list[i])
        gap_index=[]
        if word_len < 5: 
            no_of_gap=1
        elif word_len >= 5 and word_len < 10:
            no_of_gap=2
        elif word_len >= 10 and word_len < 15:
            no_of_gap=3
        else:
            no_of_gap=4
        gap_index=np.random.choice(np.random.randint(1,word_len,word_len-1),no_of_gap, replace=False)
        word_split=""
        for ii in range(0,word_len):
            if ii in gap_index:
                word_split=word_split+"_"
            else:
                word_split=word_split+cur_word[ii]
        print("cur_word", cur_word, "word_split",word_split)
        spelling_test_word[cur_word]= word_split
        
    spelling_meaning={}
    for i in spelling_test_word:
        spelling_meaning[i]=original_englishwords[i]
        print("word",i, "spelling_meaning", spelling_meaning[i])
    
    return render_template('spell.html', q = spelling_test_word, a=spelling_meaning)

@app.route('/spell_answer', methods=['POST'])
def spell_answers():
    correct = 0
    correct_answer={} 
    correct_answer_display={}
    
    print("Inside spell_answer")
    # Loop thru answer key to validate answers received from form
    # iterates thru word
    for i in spelling_test_word.keys():
        answered = request.form[i]
        print("i <",i.strip(), "> answered <",answered.strip(), "> value <",original_englishwords[i],">" )
        
        correct_answer[i]=original_englishwords[i] 
        if i.strip() == answered.strip():
            correct = correct+1
            correct_answer_display[i]=True
            print("Correct")
        else:
            correct_answer_display[i]=False
            print("False")
    return render_template('spell_answer.html', count=correct,ca=correct_answer,cad=correct_answer_display)


@app.route('/misspelled')
def misspelled():
    return render_template('underconstruct.html')


if __name__ == '__main__':
 app.run(debug=True, port=5002,threaded=True)
