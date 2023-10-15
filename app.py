from flask import Flask, request, render_template, jsonify
import json
import os
from elasticsearch import Elasticsearch, ElasticsearchException
from configparser import ConfigParser

from flask_cors import CORS
import requests

import logging
logging.basicConfig(level=logging.DEBUG)



app = Flask(__name__)
CORS(app)

# Read configuration
config = ConfigParser()
config.read('config.ini')
datasource = config.get('General', 'datasource')
es_url = config.get('ElasticSearch', 'url') if datasource == 'DB' else None
llm_url = config.get('LLM', 'llm_url')

if datasource == 'DB':
    es = Elasticsearch([es_url])


@app.route('/')
def index():
    return render_template('index2.html')

@app.route('/v1')
def index_v1():
    return render_template('index1.html')

@app.route('/v2')
def index_v2():
    return render_template('index.html')

@app.route('/v4')
def index_v4():
    return render_template('index4.html')

@app.route('/iep_template')
def iep_template():
    return render_template('iep_template.html')

@app.route('/api/iep_questions', methods=['GET'])
def get_iep_questions():
    with open('iep_template.json', 'r') as f:
        iep_data = json.load(f)
    return jsonify(iep_data)


@app.route('/get_iep_template', methods=['GET'])
def get_iep_template():
    age = request.args.get('age')
    student_type = request.args.get('student_type')
    doc_id = f"{age}_{student_type}"

    if datasource == 'DB':
        try:
            res = es.get(index="iep_templates", id=doc_id)
            return jsonify(res['_source']), 200
        except Exception as e:
            # Log the exception for debugging
            print(f"Elasticsearch fetch failed: {e}")
            # Fallback to file-based fetch
            print("Falling back to file-based fetch.")

    # File-based fetch (used as fallback if DB fetch fails)
    file_path = f"iep_templates/{age}/{student_type}.json"
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            data = json.load(f)
        return jsonify(data), 200
    else:
        return jsonify({"error": "File not found"}), 404



def save_to_db(age, student_type, updated_data):
    doc_id = f"{age}_{student_type}"
    try:
        es.index(index="iep_templates", id=doc_id, body=updated_data)
        return jsonify({"message": "Successfully updated in DB"}), 200
    except ElasticsearchException as e:
        return str(e), 500

def save_to_file(age, student_type, updated_data):
    file_path = f"iep_templates/{age}/{student_type}.json"
    if os.path.exists(file_path):
        with open(file_path, 'w') as f:
            json.dump(updated_data, f)
        return jsonify({"message": "Successfully updated in file"}), 200
    else:
        return jsonify({"error": "File not found"}), 404

@app.route('/save_iep_template', methods=['POST'])
def save_iep_template():
    content = request.get_json()
    age = content['age']
    student_type = content['student_type']
    updated_data = content['data']

    if datasource == 'DB':
        try:
            return save_to_db(age, student_type, updated_data)
        except Exception as e:
            print(f"DB save failed: {e}")
            return jsonify({"error": "DB update failed, update not supported in file-based storage"}), 500
    else:
        return save_to_file(age, student_type, updated_data)



@app.route('/get_ai_answer', methods=['POST'])
def get_ai_answer():
    try:
        content = request.get_json()
        if not all(k in content for k in ("age", "student_type", "data")):
            return jsonify({"error": "Missing required fields"}), 400

        age = content['age']
        student_type = content['student_type']
        iep_template = content['data']


        iep_template_dict = json.loads(iep_template)

        # Extract and reformat
        # Determine the formatted student_type
        if student_type == 'special_need':
            formatted_student_type = 'SpecialNeed'
        elif student_type == 'typical':
            formatted_student_type = 'Typical'
        else:
            # Handle other cases or throw an error
            formatted_student_type = 'Unknown'
        new_iep_template = [
            {
                "question": entry["question"],
                "ParentAnswer": entry["ParentAnswer"]
            }
            for entry in iep_template_dict["IEP_Template_Age{}_{}".format(age, formatted_student_type)]
        ]

        
        new_iep_template_str = json.dumps(new_iep_template, indent=2)

        print("updated_template:", new_iep_template_str)

        # Create the key for the prompt based on the student type and age
        key_for_prompt = f"IEP_Template_Age{age}_{student_type}"

        # Create the prompt string
        prompt_str = f"[INST]<<SYS>>\nYou are simulating a parent's responses for questions related to an Individualized Education Plan (IEP) for a {student_type} {age}-year-old student. Answer honestly as if you are the parent of the student and maintain the JSON-like format.\n<</SYS>>\n\n{key_for_prompt}: {new_iep_template_str}\n[/INST]"


        if not new_iep_template_str:
            return jsonify({"error": "Invalid IEP template data"}), 400

        # Create the API payload
        payload = {
            "top_p": 0.3,
            "temperature": 0.1,
            "max_gen_len": 4000,
            "do_sample": True,
            "prompt": prompt_str
        }
        
        # Call the language model API and get the response
        response = requests.post(llm_url, json=payload)

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": "Failed to get response from language model"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/get_iep_assessment', methods=['POST'])
def get_iep_assessment():
    try:
        content = request.get_json()
        if not all(k in content for k in ("question", "parentAnswer")):
            return jsonify({"error": "Missing required fields"}), 400

        question = content['question']
        parentAnswer = content['parentAnswer']
        age = content['age']
        student_type = content['student_type']


        

        # Create the updated prompt string for IEP Assessment with only the score embedded in recommendation
        prompt_str = f"""[INST]<<SYS>>
        You are an expert educator specialized in creating Individualized Education Plans for {age}-year-old students of type {student_type}. Based on the given question and the parent's answer, provide a recommendation for an IEP Assessment. At the end of your recommendation, include a score based on the student's current level. Use the scoring criteria below for internal reference, but do not discuss the levels in the recommendation.

        - Level 1: Score should be 0.8 to 1
        - Level 2: Score should be 0.6 to 0.79
        - Level 3: Score should be 0.3 to 0.59
        - Level 4: Score should be below 0.3

        Please conclude your recommendation text with 'Score= X.X', without starting a new line or a separate section.
        <</SYS>>

        Question: '{question}'
        ParentAnswer: '{parentAnswer}'

        Recommendation: [/INST]"""


        # Create the API payload
        payload = {
            "top_p": 0.3,
            "temperature": 0.1,
            "max_gen_len": 4000,
            "do_sample": True,
            "prompt": prompt_str
        }
        
        # Call the language model API and get the response
        response = requests.post(llm_url, json=payload)

        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": "Failed to get response from language model"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


app.run(host='0.0.0.0', port=8891, debug=True, use_reloader=True)
