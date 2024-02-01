import hashlib
import io
import json
import random
import traceback

import cv2
import firebase_admin
import functions_framework
import numpy as np
from firebase_admin import auth, credentials, firestore, storage
from flask import Flask, escape, make_response, send_file

import batch_operation
import firebase_initializer
from core.clova import general
from core.clova_ext import table_to_csv_text
from core.document_similarity import check_document_similarity
from core.gpt import completion
from core.gpt_ext import create_embeddings_from_csv
from core.openai_client import get_openai_client
from core.pdf2img import pdf2img, pdf2imgs
from core.skew_detection import detect
from core.workflow_export import workflow_export
from core.workflow_read import workflow_read
from js_utils import (
    davinci_003_base_prompt,
    gpt_chat_base_prompt,
    gpt_system_chat_base_prompt,
    unify_alphas,
    unify_numbers,
    unify_symbols,
)
from master_utils import create_vectors_for_csv_mapping_for_requirements
from pkg.cors.main import Cors
from recog_utils import (
    get_ai_csv_path_with_master,
    load_master_csv_data,
    operate_uploaded_data,
)
from utils import verified_uid

temp = None


@functions_framework.http
def perform_general_ocr(request):
    if request.method == "OPTIONS":
        return Cors.options_cors()

    # get uid
    uid = verified_uid(request)

    # receive file from request
    file = request.files['file']

    # convert file to numpy array
    npimg = np.fromstring(file.read(), np.uint8)
    mat = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    if request.form["auto_rotate"] == "1":
        mat = detect(mat)

    # perform general ocr
    result = general(mat, False)

    temp = result

    return (result, 200, Cors.cors_headers())


@functions_framework.http
def auto_rotate_image(request):
    if request.method == "OPTIONS":
        return Cors.options_cors()

    # get uid
    uid = verified_uid(request)

    # receive file from request
    file = request.files['file']

    # TODO: matsudo for the future replace fast rotate image

    # convert file to numpy array
    npimg = np.fromstring(file.read(), np.uint8)
    mat = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    mat = detect(mat)

    _, png_image = cv2.imencode(".png", mat)

    response = make_response(send_file(io.BytesIO(png_image), mimetype="image/png"))

    response.headers = Cors.cors_headers()
    return response


@functions_framework.http
def pdf_to_image(request):
    if request.method == "OPTIONS":
        return Cors.options_cors()

    # get uid
    uid = verified_uid(request)

    # receive file from request
    file = request.files['file']

    # convert file to numpy array
    binary = file.read()
    mat = pdf2img(binary)

    _, png_image = cv2.imencode(".png", mat)

    response = make_response(
        send_file(io.BytesIO(png_image), mimetype="image/png"))
    print(response)
    response.headers = Cors.cors_headers()
    return response


@functions_framework.http
def deal_uploaded_data_with_ids(request):
    if request.method == "OPTIONS":
        return Cors.options_cors()

    # read query params
    company_id = request.args.get("company_id")
    work_id = request.args.get("work_id")
    uploaded_id = request.args.get("uploaded_id")
    uploadingStatus = request.args.get("uploading_status")

    if batch_operation.deal_uploaded_data_preprocess(company_id, work_id, uploaded_id, uploadingStatus):
        return ("", 200, Cors.cors_headers())
    else:
        return ("", 400, Cors.cors_headers())


@functions_framework.http
def add_master_training_requirement(request):
    if request.method == "OPTIONS":
        return Cors.options_cors()

    # read post params
    company_id = request.form["company_id"]
    master_group_id = request.form["master_group_id"]
    master_id = request.form["master_id"]
    target_column_name = request.form["target_column_name"]

    # `companies/${companyId}/master_groups/${masterGroupId}/masters/${masterId}/master_training_requirements`
    col = firestore.client().collection(
        f"companies/{company_id}/master_groups/{master_group_id}/masters/{master_id}/master_training_requirements")

    # hash target column name
    hashed_target_column_name = hashlib.md5(
        target_column_name.encode()).hexdigest()

    if not col.document(hashed_target_column_name).get().exists:
        # add
        col.document(hashed_target_column_name).set({
            "target_column_name": target_column_name,
            "created_at": firestore.SERVER_TIMESTAMP,
        })

    return ("", 200, Cors.cors_headers())


@functions_framework.http
def create_vectors_for_csv_mapping(request):
    if request.method == "OPTIONS":
        return Cors.options_cors()

    # get uid
    uid = verified_uid(request)

    # read vars
    csv_file_name = request.form["csv_file_name"]
    target_column = request.form["target_column"]
    engine = request.form["engine"]

    # get file from storage
    bucket = storage.bucket()
    bucket_file_path = csv_file_name
    # get binary from file
    data_bytes = bucket.blob(bucket_file_path).download_as_string()
    # bytes to string
    data_str = data_bytes.decode("utf-8")

    # saving filename
    name = csv_file_name + \
           hashlib.md5(target_column.encode()).hexdigest() + ".vectors"

    # create vectors
    result = create_embeddings_from_csv(data_str, target_column, engine, uid)
    dumped = json.dumps(result).encode("utf-8")

    # upload to bucket
    bucket.blob(name).upload_from_string(dumped)

    return (name, 200, Cors.cors_headers())


@functions_framework.http
def create_vectors_for_csv_mapping_to_satisfy_requirement(request):
    if request.method == "OPTIONS":
        return Cors.options_cors()

    # get uid
    uid = verified_uid(request)

    # read vars
    engine = request.form["engine"]
    company_id = request.form["company_id"]
    master_group_id = request.form["master_group_id"]
    master_id = request.form["master_id"]
    master_historical_id = request.form["master_historical_id"]

    create_vectors_for_csv_mapping_for_requirements(
        engine, company_id, master_group_id, master_id, master_historical_id, uid, False)

    return ("", 200, Cors.cors_headers())


@functions_framework.http
def check_if_vectorizing_required_for_the_master(request):
    if request.method == "OPTIONS":
        return Cors.options_cors()

    # get uid
    uid = verified_uid(request)

    # read vars
    engine = request.form["engine"]
    company_id = request.form["company_id"]
    master_group_id = request.form["master_group_id"]
    master_id = request.form["master_id"]
    master_historical_id = request.form["master_historical_id"]

    # dry run
    processing_count = create_vectors_for_csv_mapping_for_requirements(
        engine, company_id, master_group_id, master_id, master_historical_id, uid, True)

    if processing_count > 0:
        return ("1", 200, Cors.cors_headers())
    else:
        return ("0", 200, Cors.cors_headers())


@functions_framework.http
def create_script_from_prompt(request):
    if request.method == "OPTIONS":
        return Cors.options_cors()

    # get uid
    uid = verified_uid(request)

    # read vars
    prompt = request.form["prompt"]
    unifySymbols = request.form["unify_symbols"]
    unifyNumbers = request.form["unify_numbers"]
    unifyAlphas = request.form["unify_alphas"]
    engine = "text-davinci-003"
    client = get_openai_client()

    # get engine and use text-davinci-003 if not specified
    if "engine" in request.form and request.form["engine"] != "" and request.form["engine"] != None:
        engine = request.form["engine"]

    # decide base prompt
    if engine == "text-davinci-003":
        # davinci-003
        base_prompt = davinci_003_base_prompt
    else:
        # other engines
        base_prompt = gpt_chat_base_prompt

    # system base prompt for chat engines
    base_prompt_for_chat = gpt_system_chat_base_prompt

    # completion
    result, total_tokens = completion(base_prompt.replace(
        "<INPUT>", prompt), client, engine, uid, base_prompt_for_chat)

    # parse
    if "```javascript" in result:
        # parse code that is between ```javascript and ```
        code_start = result.find("```javascript")
        code_end = result.find("```", code_start + 1)
        result = result[code_start + 13:code_end]
    else:
        # result only contains code
        # do nothing
        pass

    # append base code
    ret = "let text = \"<INPUT_DATA>\";"
    ret += "\n"

    # append unify code for symbols if required
    if unifySymbols == "1":
        ret += unify_symbols
        ret += "\n"

    # append unify code for numbers if required
    if unifyNumbers == "1":
        ret += unify_numbers
        ret += "\n"

    # append unify code for alphas if required
    if unifyAlphas == "1":
        ret += unify_alphas
        ret += "\n"
    ret += result
    ret += "\n"

    return (ret, 200, Cors.cors_headers())


@functions_framework.http
def run_read(request):
    if request.method == "OPTIONS":
        return Cors.options_cors()

    # get uid
    uid = verified_uid(request)
    print(uid)

    # receive file from request
    # file = request.files['file']
    company_id = request.form["company_id"]
    work_id = request.form["work_id"]
    template_id = request.form["template_id"]
    auto_rotate = request.form["auto_rotate"]
    staged = False
    if "staged" in request.form:
        staged = request.form["staged"] == "1"
    # receive file from request
    if "file_path" in request.form:
        file_path = request.form['file_path']
        # get file from storage
        bucket = storage.bucket()
        bucket_file_path = file_path
        # get binary from file
        str = bucket.blob(bucket_file_path).download_as_string()
        file = io.BytesIO()
        file.write(str)
        file.seek(0)
    else:
        file = request.files["file"]

    # convert file to numpy array
    npimg = np.fromstring(file.read(), np.uint8)
    mat = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    if auto_rotate == "1":
        mat = detect(mat)

    # firestore db from firebase_admin
    db = firestore.client()

    # get document from firestore (path: companies/{company_id}/works/{work_id}/templates/{template_id})
    doc = db.collection(
        "companies").document(company_id).collection("works").document(work_id).collection("templates").document(
        template_id).get()
    json_dict = doc.to_dict()["workflowProcessor"]

    readers = json_dict["read"]
    readers_page_zero = readers["*"]

    export_dict = {}
    tmp_dict = {}
    on_memory_dict = {}

    actual_costs = {
        "general-calls": 3,
        "general-table-calls": 0,
        "clova-rect-calls": 0,
        "natural-tokens": 0,
        "items": 0,
    }

    for reader in readers_page_zero:
        try:
            # in the api, you should read file from gcs
            if reader["provider"] == "openai-gpt" or reader["provider"] == "openai-gpt3":
                prompt_id = reader["base_prompt"]
                # get value from firestore, path: settings/private/prompt/{prompt_id}
                doc = db.collection("settings").document(
                    "private").collection("prompt").document(prompt_id).get()
                prompt = doc.to_dict()["prompt"]
                reader["base_prompt"] = prompt
            elif reader["provider"] == "clova-rect":
                domain_id = reader["domain"]
                # get value from firestore, path: settings/private/clova_domains/{domain_id}
                doc = db.collection("settings").document(
                    "private").collection("clova_domains").document(domain_id).get()
                domain_url = doc.to_dict()["url"]
                domain_secret = doc.to_dict()["secret"]
                reader["domain_url"] = domain_url
                reader["domain_secret"] = domain_secret
                templateIds_str = reader["templateIds"]
                templateIds_int = [int(i) for i in templateIds_str.split(",")]
                reader["templateIds"] = templateIds_int
            elif reader["provider"] == "map":
                csv_file_bucket_path, data_str = load_master_csv_data(
                    reader, db, company_id, staged)

                reader["csv_data"] = data_str
                # get vectors if strategy is ai
                if reader["strategy"] == "ai":
                    if 'master' in reader:
                        bucket_file_path = get_ai_csv_path_with_master(
                            csv_file_bucket_path, reader["csv_column_from"])
                        reader["vectors_engine"] = "text-embedding-ada-002"
                    else:
                        bucket_file_path = reader["vectors_file_name"]

                    # get file from storage
                    bucket = storage.bucket()
                    # get binary from file
                    try:
                        data_bytes = bucket.blob(
                            bucket_file_path).download_as_string()
                    except:
                        print("vectors file not found")
                    # bytes to string
                    data_str = data_bytes.decode("utf-8")
                    reader["vectors_data"] = json.loads(data_str)
            workflow_read(reader, mat, export_dict,
                          on_memory_dict, tmp_dict, actual_costs, uid)
        except:
            traceback.print_exc()
            return (json.dumps({"error": "error", "at": reader["id"]}), 500, Cors.cors_headers())

    # return export_json with cors_headers
    return (json.dumps({
        "actual_costs": actual_costs,
        "export_dict": export_dict,
    }), 200, Cors.cors_headers())


@functions_framework.http
def run_write(request):
    if request.method == "OPTIONS":
        return Cors.options_cors()

    # get uid
    uid = verified_uid(request)

    # receive file from request
    # file = request.files['file']
    company_id = request.form["company_id"]
    work_id = request.form["work_id"]
    template_id = request.form["template_id"]
    input_data = request.form["input_data"]
    required_column_overwrite = ""
    if "required_column" in request.form and request.form["required_column"] != None:
        required_column_overwrite = request.form["required_column"]

    # firestore db from firebase_admin
    db = firestore.client()

    # get document from firestore (path: companies/{company_id}/works/{work_id}/templates/{template_id})
    doc = db.collection(
        "companies").document(company_id).collection("works").document(work_id).collection("templates").document(
        template_id).get()
    json_dict = doc.to_dict()["workflowProcessor"]

    # input_data as json
    input_data = json.loads(input_data)

    csv = json_dict["write"]["spreadsheet"]["csv"]

    if "write_csv" in request.form:
        csv = request.form["write_csv"]

    result = workflow_export(json_dict["write"], input_data,
                             csv)

    if required_column_overwrite != "":
        json_dict["write"]["required_column"] = required_column_overwrite

    # check required
    if "required_column" in json_dict["write"] and json_dict["write"]["required_column"] != "":
        try:
            # get header index
            header_index = result[0].index(
                json_dict["write"]["required_column"])
            print(json_dict["write"]["required_column"])
            if header_index >= 0:
                new_result = []
                new_result.append(result[0])
                for row in result[1:]:
                    if row[header_index] != "":
                        new_result.append(row)
                result = new_result
        except:
            pass

    # return export_json with cors_headers
    return (json.dumps(result), 200, Cors.cors_headers())


@functions_framework.http
def run_get_matched_template_id(request):
    if request.method == "OPTIONS":
        return Cors.options_cors()

    # get uid
    uid = verified_uid(request)

    # receive file from request
    file = request.files['file']
    company_id = request.form["company_id"]
    work_id = request.form["work_id"]
    auto_rotate = request.form["auto_rotate"]

    # firestore db from firebase_admin
    db = firestore.client()

    # get documents from firestore (path: companies/{company_id}/works/{work_id}/templates)
    docs = db.collection(
        "companies").document(company_id).collection("works").document(work_id).collection("templates").stream()

    # convert file to numpy array
    npimg = np.fromstring(file.read(), np.uint8)
    mat = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    if auto_rotate == "1":
        mat = detect(mat)

    # perform general ocr
    result = general(mat, False)

    # get matched template id
    # foreach docs
    largest = 0
    largest_id = ""
    largest_comb = None
    for doc in docs:
        json_dict = doc.to_dict()
        if "referenceFields" not in json_dict:
            continue
        reference_fields = json_dict["referenceFields"]
        sim, comb = check_document_similarity(
            reference_fields, result["images"][0]["fields"])
        print(str(sim) + ": " + doc.id)
        if largest < sim and sim > 0.6:
            print(comb)
            largest = sim
            largest_id = doc.id
            largest_comb = comb

    result = dict()
    result["id"] = largest_id
    result["similarity"] = largest
    result["combination"] = largest_comb

    return (json.dumps(result), 200, Cors.cors_headers())


@functions_framework.http
def run_read_one(request):
    if request.method == "OPTIONS":
        return Cors.options_cors()

    # get uid
    uid = verified_uid(request)
    print(uid)

    # receive file from request
    # file = request.files['file']
    company_id = request.form["company_id"]
    work_id = request.form["work_id"]
    template_id = request.form["template_id"]
    document_id = request.form["document_id"]
    row_col_map = json.loads(request.form["row_col_map"])

    from recog_utils import read_workflow_one
    export_dict = read_workflow_one(
        company_id, work_id, template_id, dict(), document_id, uid, row_col_map)

    # return export_json with cors_headers
    return (json.dumps({
        "export_table": export_dict,
    }), 200, Cors.cors_headers())


@functions_framework.http
def health():
    return ("", 200, Cors.cors_headers())


@functions_framework.http
def wrap(request):
    func = request.args.get("func")

    if func == "perform_general_ocr":
        return perform_general_ocr(request)
    elif func == "auto_rotate_image":
        return auto_rotate_image(request)
    elif func == "pdf_to_image":
        return pdf_to_image(request)
    elif func == "run_read":
        return run_read(request)
    elif func == "run_write":
        return run_write(request)
    elif func == "run_get_matched_template_id":
        return run_get_matched_template_id(request)
    else:
        return ("", 404, Cors.cors_headers())
