from flask import Flask, render_template, request, jsonify, session
from flask import redirect, url_for
import os
import io
import re
import ast
import boto3
from botocore.exceptions import NoCredentialsError
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
from mysql.connector.cursor import MySQLCursorDict 
from flask_session import Session
from flask_kvsession import KVSessionExtension
from flask_dropzone import Dropzone
import redis

# Configure AWS S3
AWS_ACCESS_KEY = 'AKIAUG7BJ6UPZUFH6XVH'
AWS_SECRET_KEY = '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'
S3_BUCKET_NAME = 'skillsyncbucket'
S3_REGION = 'Asia Pacific (Singapore) ap-southeast-1'

s3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)

# Get the Heroku database URL
#db_url = os.getenv("JAWSDB_URL")
db_url = 'mysql://ipozjqf4nynf5g8t:gz1okb91qs7xf8g3@bv2rebwf6zzsv341.cbetxkdyhwsb.us-east-1.rds.amazonaws.com:3306/ydmso128kp8kj4zj'

# Print db_config for debugging
print("db_url:", db_url)

# Update config to use JAWSDB_URL
db_config = {
    'user': db_url.split(':')[1].split('//')[1],
    'password': db_url.split(':')[2].split('@')[0],
    'host': db_url.split('@')[1].split(':')[0],
    'database': db_url.split('/')[3].split('?')[0],
    'port': db_url.split('@')[1].split(':')[1].split('/')[0],
}

# Print db_config for debugging
print("db_config:", db_config)

def get_job_postings_from_db():
    """Fetch job postings from the MySQL database."""
    try:
        # Use the database URL from the configuration
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)

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
        # Close the cursor and connection, if they exist
        if cursor:
            cursor.close()
        if connection:  
            connection.close()

# Replace the CSV reading code with the database fetching code
data_df = get_job_postings_from_db()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Configure Flask app to use Redis for sessions
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_REFRESH_EACH_REQUEST'] = False
app.config['SESSION_KEY_PREFIX'] = 'skillsyncv2'  # Replace with a unique prefix
app.config['SESSION_REDIS'] = redis.StrictRedis.from_url('redis://default:qb1YLSxluzO5Y6RtPsx6INoN7RiRf6Oy@redis-19538.c267.us-east-1-4.ec2.cloud.redislabs.com:19538')
app.config["SESSION_COOKIE_NAME"] = "session"
# Expire sessions after 5 minutes of inactivity
app.config['SESSION_REDIS_EXPIRE_AFTER'] = 300

# Create Redis client
redis_client = redis.StrictRedis.from_url('redis://default:qb1YLSxluzO5Y6RtPsx6INoN7RiRf6Oy@redis-19538.c267.us-east-1-4.ec2.cloud.redislabs.com:19538')

# Initialize Flask-Session
Session(app)

# Initialize Flask-KVSession
kvsession = KVSessionExtension(app)

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

@app.route('/test-redis')
def test_redis():
    try:
        redis_client.ping()
        print("Connected to Redis successfully!")
    except Exception as e:
        print("Error connecting to Redis:", e)

    try:
        redis_client.set('test_key', 'test value')
        print("Set key in Redis")
    except Exception as e:
        print("Error setting Redis key:", e)

    try:
        value = redis_client.get('test_key')
        print("Got value from Redis:", value)
    except Exception as e:
        print("Error getting Redis key:", e)

    # Delete test key
    redis_client.delete('test_key')

    return "Testing Redis completed"

@app.route('/insight')
def insight():
    # Any data processing or logic for the insight page can be done here
    return render_template('insight.html')

# Define a function to check if a file has a PDF extension
def is_pdf(filename):
    return bool(re.match(r'.*\.pdf$', filename, re.IGNORECASE))

basedir = os.path.abspath(os.path.dirname(__file__))

app.config.update(
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
            try:
                # Upload the file to S3
                s3.upload_fileobj(file, S3_BUCKET_NAME, file.filename)
                print("File uploaded successfully to S3:", file.filename)

                # Save filename in session
                session['resume_filename'] = file.filename
                print("Filename in S3:", session.get('resume_filename'))
                
                # Store the S3 file URL in the session
                s3_file_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{file.filename}"
                session['resume_s3_url'] = s3_file_url
                print("Filename URL in S3:", session.get('resume_s3_url'))

                return redirect(url_for('match'))
            
            except NoCredentialsError:
                return 'Credentials not available.'
            except Exception as e:
                return f'An error occurred: {str(e)}'
        else:
            return 'Invalid file format. Please upload a PDF file.'

    if request.method == 'GET':
        if 'match_btn' in request.args:
            # Match button was clicked
            # Build file path
            
            # Get filename from session 
            filename = session.get('resume_filename')

            if filename:
                print("Processing file:", filename, flush=True)

                # Read the file content from S3
                try:
                    response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=str(filename))
                    file_content = response['Body'].read()

                    # Create a file-like object from the bytes data
                    file_obj = io.BytesIO(file_content)
                    
                    # Extract text from the uploaded resume PDF
                    pdf_reader = PyPDF2.PdfReader(file_obj)
                    extracted_text = ''.join(page.extract_text() for page in pdf_reader.pages)

                    print("Extracted text from resume:", extracted_text)
                
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

                except Exception as e:
                    print("Error reading file from S3:", str(e))

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

@app.after_request
def set_cookie(response):
    if "session_id" in session:
        print(f"Type of session_id: {type(session['session_id'])}")
        response.set_cookie(app.config["SESSION_COOKIE_NAME"], str(session["session_id"]))
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
