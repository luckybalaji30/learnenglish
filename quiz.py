
from flask import Flask, render_template, request
import numpy as np
import copy
import os, datetime
from flask import flash, redirect, url_for
from werkzeug.utils import secure_filename
import pandas as pd


app = Flask(__name__)

# global variables
UPLOAD_FOLDER = '/Users/balajis/Balaji/Learning/Python/pranav01/'
ALLOWED_EXTENSIONS = {'csv'}
filename="pranavawordlist.csv"

fullfilename=os.path.join(UPLOAD_FOLDER,filename)
data = pd.read_csv(fullfilename)
original_englishwords={}
englishwords={}
words=[]
spell_word_list=[]
meanings=[]


no_of_choices=4
no_of_questions=10
original_englishwords = dict(zip(data.Word, data.Meaning))
englishwords = copy.deepcopy(original_englishwords)
words=[i for i in englishwords.keys()]
meanings=[i for i in englishwords.values()]
    

def refresh_word():
    global words, meanings, englishwords, original_englishwords,spell_word_list
    prev_cnt=len(words)
    data = pd.read_csv(fullfilename)
    original_englishwords = dict(zip(data.Word, data.Meaning))
    englishwords = copy.deepcopy(original_englishwords)
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

@app.route('/')
def index():
    p,c = refresh_word()
    return render_template('index.html')

@app.route('/upload')
def upload():
    return render_template('upload.html')

@app.route('/refresh')
def refresh():
    p,c= refresh_word()
    return render_template('data_refreshed.html',
                                    p=p, c=c)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/uploadsubmit', methods=['GET', 'POST'])
def upload_file():
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
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            f_filename = os.path.join(UPLOAD_FOLDER,filename)
            # Get the create time of the file
            create_time = os.path.getctime( f_filename )
            
            # get the readable timestamp format 
            format_time = datetime.datetime.fromtimestamp( create_time )
            
            #convert time into string
            format_time_string = format_time.strftime("%Y_%m_%d_%H_%M_%S") # e.g. 2015_01_01_09_00_00
            
            #consruct the new name of the file
            oldfile = f_filename + format_time_string 

            if os.path.exists(f_filename):
                os.rename(f_filename,oldfile)
                
            file.save(os.path.join(UPLOAD_FOLDER,filename))
            refresh_word()
            return render_template('uploaded_file.html',
                                    filename=filename)
    return

@app.route('/quiz')
def quiz():
    cur_question_no=0
    questionWordList=[]
    global questions_shuffles
    questions_shuffles={}
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
    return render_template('misspelled.html')

@app.route('/underconstruction')
def underconstruction():
    return render_template('underconstruct.html')

if __name__ == '__main__':
 app.run(port=5002)
