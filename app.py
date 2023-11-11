from flask import Flask, render_template, request, jsonify, session
from flask import redirect, url_for
import os
import re
import ast
import secrets
import PyPDF2
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
import mysql.connector
from flask_session import Session
from flask_dropzone import Dropzone

# Update this line in your code
db_url = os.getenv("JAWSDB_URL", "mysql://root:@localhost/skillsync_db")

# Database configuration
db_config = {
    "url": db_url,
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "skillsync_db"
}

def get_job_postings_from_db():
    """Fetch job postings from the MySQL database."""
    try:
        # Use the database URL from the configuration
        connection = mysql.connector.connect(host=db_config["url"], charset='utf8mb4', cursorclass=mysql.cursors.DictCursor)
        cursor = connection.cursor()
        
        # Query to fetch data
        query = "SELECT * FROM job_data"
        cursor.execute(query)
        
        # Fetch all rows
        rows = cursor.fetchall()

        return pd.DataFrame(rows)
    
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None
    finally:
        # Close the cursor and connection
        cursor.close()
        connection.close()

# Replace the CSV reading code with the database fetching code
data_df = get_job_postings_from_db()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Configure session to use the filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "C:\\Users\\Fikri\\Downloads\\Version 4\\SkillSyncV2\\session"
Session(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def data():
    # Replace NaN with "Not Specified" before sending as JSON
    clean_data_df = data_df.fillna("Not Specified")
    return jsonify(clean_data_df.to_dict(orient='records'))

@app.route('/debug_session')
def debug_session():
    return jsonify(dict(session))

@app.route('/insight')
def insight():
    # Any data processing or logic for the insight page can be done here
    return render_template('insight.html')

# Define a function to check if a file has a PDF extension
def is_pdf(filename):
    return bool(re.match(r'.*\.pdf$', filename, re.IGNORECASE))

basedir = os.path.abspath(os.path.dirname(__file__))

app.config.update(
    UPLOADED_PATH=os.path.join(basedir, 'resumes'),
    # Flask-Dropzone config:
    DROPZONE_MAX_FILE_SIZE=3,
    DROPZONE_MAX_FILES=30,
)

dropzone = Dropzone(app)

@app.route('/match', methods=['POST', 'GET'])
def match():

    ranked_postings = None
    page = request.args.get('page', default=1, type=int)
    per_page = 5  # Number of items per page
    items = []
    num_pages = 0
    extracted_skills = []


    if request.method == 'POST':
        # Save on upload
        file = request.files['file']
        if file and is_pdf(file.filename):
            print("Uploaded file:", file.filename, flush=True)
            # Save the PDF file or perform any other necessary actions
            file.save(os.path.join(app.config['UPLOADED_PATH'], file.filename))
            session['resume_filename'] = file.filename
            return redirect(url_for('match'))
        else:
            return 'Invalid file format. Please upload a PDF file.'

    if request.method == 'GET':
        if 'match_btn' in request.args:
            # Match button was clicked
            # Build file path
            filename = session.get('resume_filename')
            file_path = os.path.join(app.config['UPLOADED_PATH'], filename)
            if filename:
                print("Processing file:", filename, flush=True)
                # Extract text from the uploaded resume PDF
                with open(file_path, 'rb') as pdf_file:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    extracted_text = ''.join(page.extract_text() for page in pdf_reader.pages)


                # Dictionary for skills and tools mapping, in order to have a correct naming
                keywords_skills = {
                    'airflow': 'Airflow', 'alteryx': 'Alteryx', 'asp.net': 'ASP.NET', 'atlassian': 'Atlassian', 
                    'excel': 'Excel', 'power_bi': 'Power BI', 'tableau': 'Tableau', 'srss': 'SRSS', 'word': 'Word', 
                    'unix': 'Unix', 'vue': 'Vue', 'jquery': 'jQuery', 'linux/unix': 'Linux / Unix', 'seaborn': 'Seaborn', 
                    'microstrategy': 'MicroStrategy', 'spss': 'SPSS', 'visio': 'Visio', 'gdpr': 'GDPR', 'ssrs': 'SSRS', 
                    'spreadsheet': 'Spreadsheet', 'aws': 'AWS', 'hadoop': 'Hadoop', 'ssis': 'SSIS', 'linux': 'Linux', 
                    'sap': 'SAP', 'powerpoint': 'PowerPoint', 'sharepoint': 'SharePoint', 'redshift': 'Redshift', 
                    'snowflake': 'Snowflake', 'qlik': 'Qlik', 'cognos': 'Cognos', 'pandas': 'Pandas', 'spark': 'Spark', 'outlook': 'Outlook',
                    'sql' : 'SQL', 'python' : 'Python', 'r' : 'R', 'c':'C', 'c#':'C#', 'javascript' : 'JavaScript', 'js':'JS', 'java':'Java', 
                    'scala':'Scala', 'sas' : 'SAS', 'matlab': 'MATLAB', 'c++' : 'C++', 'c/c++' : 'C / C++', 'perl' : 'Perl','go' : 'Go',
                    'typescript' : 'TypeScript','bash':'Bash','html' : 'HTML','css' : 'CSS','php' : 'PHP','powershell' : 'Powershell',
                    'rust' : 'Rust', 'kotlin' : 'Kotlin','ruby' : 'Ruby','dart' : 'Dart','assembly' :'Assembly',
                    'swift' : 'Swift','vba' : 'VBA','lua' : 'Lua','groovy' : 'Groovy','delphi' : 'Delphi','objective-c' : 'Objective-C',
                    'haskell' : 'Haskell','elixir' : 'Elixir','julia' : 'Julia','clojure': 'Clojure','solidity' : 'Solidity',
                    'lisp' : 'Lisp','f#':'F#','fortran' : 'Fortran','erlang' : 'Erlang','apl' : 'APL','cobol' : 'COBOL',
                    'ocaml': 'OCaml','crystal':'Crystal','javascript/typescript' : 'JavaScript / TypeScript','golang':'Golang',
                    'nosql': 'NoSQL', 'mongodb' : 'MongoDB','t-sql' :'Transact-SQL', 'no-sql' : 'No-SQL','visual_basic' : 'Visual Basic',
                    'pascal':'Pascal', 'mongo' : 'Mongo', 'pl/sql' : 'PL/SQL','sass' :'Sass', 'vb.net' : 'VB.NET','mssql' : 'MSSQL',
                }

                # Extract skills from the resume
                extracted_skills = [keywords_skills[skill] for skill in keywords_skills if re.search(skill, extracted_text, re.IGNORECASE)]
                print(f"Extracted skills from resume: {extracted_skills}")

                # Get skills from job posting
                data_df['extracted_skills'] = data_df['skill_token'].apply(lambda skills_str: ast.literal_eval(skills_str))

                # Calculate and store the skill gap in a new column
                # Convert extracted skills from the resume to a set
                resume_skills_set = set(extracted_skills)
                data_df['skill_gap'] = data_df['extracted_skills'].apply(lambda job_skills: list(set(job_skills) - resume_skills_set))

                # TF-IDF and cosine similarity
                vectorizer = TfidfVectorizer()
                resume_skills_vector = vectorizer.fit_transform([' '.join(extracted_skills)])

                match_scores = []
                for _, row in data_df.iterrows():
                    job_skills_vector = vectorizer.transform([' '.join(row['extracted_skills'])])
                    similarity_score = cosine_similarity(resume_skills_vector, job_skills_vector)[0][0]
                    match_scores.append(similarity_score)

                print(f"Number of job postings: {len(data_df)}")
                print(f"Match scores for first 10 postings: {match_scores[:10]}")

                data_df['match_scores'] = match_scores
                sorted_postings = data_df.sort_values(by='match_scores', ascending=False)
                ranked_postings = [(rank, row.to_dict()) for rank, (_, row) in enumerate(sorted_postings.iterrows(), start=1)]

                skill_gaps = [set(posting_skills) - set(extracted_skills) for posting_skills in data_df['extracted_skills']]

                # Store only the sorted indices in session
                sorted_indices = data_df.sort_values(by='match_scores', ascending=False).index.tolist()
                session['sorted_indices'] = sorted_indices
                session['resume_extracted_skills'] = extracted_skills

                items = ranked_postings[:per_page]

            return render_template('match.html', items=items, num_pages=num_pages, current_page=page, skills=extracted_skills)

        else:
            # Normal GET request
            print("Match button not clicked")
            # Retrieve sorted_indices from session
            sorted_indices = session.get('sorted_indices', [])
            extracted_skills = session.get('resume_extracted_skills', [])

            # Ensure that sorted_indices is not None
            if sorted_indices is None:
                sorted_indices = []

            # Logic for pagination (whether POST or GET)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            required_indices = sorted_indices[start_idx:end_idx]
            # items = [(rank + 1, data_df.loc[idx]) for rank, idx in enumerate(required_indices)]
            items = [(rank + 1, data_df.loc[idx].to_dict()) for rank, idx in enumerate(required_indices)]
    
            # print(items)

            num_pages = (len(sorted_indices) + per_page - 1) // per_page

            return render_template('match.html', items=items, num_pages=num_pages, current_page=page, skills=extracted_skills)


if __name__ == '__main__':
    app.run(debug=True)
