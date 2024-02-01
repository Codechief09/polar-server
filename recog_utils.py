import hashlib
import re
import io
import json
import time
import traceback

import cv2
import firebase_admin
import functions_framework
import numpy as np
from firebase_admin import auth, credentials, firestore, storage
from flask import Flask, escape, make_response, send_file

from core.clova import general
from core.clova_ext import table_to_csv_text
from core.document_similarity import check_document_similarity
from core.gpt_ext import create_embeddings_from_csv
from core.pdf2img import pdf2img, pdf2imgs
from core.polar_exception import (
    PolarReadNonRetriableException,
    PolarReadRetriableException,
)
from core.skew_detection import detect, detect_get_angle_only, detect_with_angles
from core.workflow_export import workflow_export
from core.workflow_read import workflow_read
from master_utils import get_ai_csv_path_with_master, load_master_csv_data
from pkg.cors.main import Cors
from utils import verified_uid


def match_template(mat, company_id, work_id, auto_rotate=False):
    # firestore db from firebase_admin
    db = firestore.client()

    # get documents from firestore (path: companies/{company_id}/works/{work_id}/templates)
    docs = db.collection(
        "companies").document(company_id).collection("works").document(work_id).collection("templates").stream()

    if auto_rotate == True:
        mat = detect(mat)

    # perform general ocr
    result = general(mat, False)

    # get matched template id
    # foreach docs
    largest = 0
    largest_id = ""
    for doc in docs:
        json_dict = doc.to_dict()
        if "referenceFields" not in json_dict:
            continue
        reference_fields = json_dict["referenceFields"]
        sim, comb = check_document_similarity(
            reference_fields, result["images"][0]["fields"])
        if largest < sim and sim > 0.6:
            largest = sim
            largest_id = doc.id

    result = dict()
    result["id"] = largest_id
    result["similarity"] = largest

    return largest_id, largest


def read_workflow(mat, company_id, work_id, template_id, auto_rotate=False, costs_dict=dict(), document_id="",
                  user_id=""):
    if auto_rotate == True:
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

    try:
        if document_id != "":
            doc = db.collection("companies_tmp").document(company_id).collection(
                "works").document(work_id).collection("read_workflow").document(document_id).get()
            if doc.exists:
                print("recovering from tmp for " + document_id)
                doc_dict = doc.to_dict()
                tmp_dict = json.loads(doc_dict["tmp_dict"])
                if tmp_dict is None:
                    tmp_dict = {}
    except:
        print("failed to recovery")
        pass

    for reader in readers_page_zero:
        try:
            # in the api, you should read file from gcs
            if reader["provider"] == 'openai-gpt' or reader["provider"] == "openai-gpt3":
                prompt_id = reader["base_prompt"]
                # get value from firestore, path: settings/private/prompt/{prompt_id}
                doc = db.collection("settings").document(
                    "private").collection("prompt").document(prompt_id).get()
                prompt = doc.to_dict()["prompt"]
                reader["base_prompt"] = prompt
            elif reader["provider"] == 'clova-rect':
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
            elif reader["provider"] == 'map':
                csv_file_bucket_path, data_str = load_master_csv_data(
                    reader, db, company_id)

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
                    data_bytes = bucket.blob(
                        bucket_file_path).download_as_string()
                    # bytes to string
                    data_str = data_bytes.decode("utf-8")
                    reader["vectors_data"] = json.loads(data_str)
        except:
            raise Exception(traceback.format_exc())
        try:
            workflow_read(reader, mat, export_dict,
                          on_memory_dict, tmp_dict, costs_dict, user_id)
        except Exception as e:
            # try to save tmp_dict to firestore /companies_tmp/{company_id}/works/{work_id}/read_workflow/{document_id}
            try:
                db.collection("companies_tmp").document(company_id).collection("works").document(work_id).collection(
                    "read_workflow").document(document_id).set({
                    "tmp_dict": json.dumps(tmp_dict),
                })
            except:
                pass
            raise e

    try:
        # save tmp_dict to firestore /companies_tmp/{company_id}/works/{work_id}/read_workflow/{document_id}
        db.collection("companies_tmp_completed").document(company_id).collection("works").document(work_id).collection(
            "read_workflow").document(document_id).set({
            "tmp_dict": json.dumps(tmp_dict),
            "export_dict": json.dumps(export_dict),
            "costs_dict": json.dumps(costs_dict),
            "template_id": template_id,
        })
    except:
        pass
    # return export_json with cors_headers
    return export_dict


def write_workflow(company_id, work_id, template_id, input_data):
    # firestore db from firebase_admin
    db = firestore.client()

    # get document from firestore (path: companies/{company_id}/works/{work_id}/templates/{template_id})
    doc = db.collection(
        "companies").document(company_id).collection("works").document(work_id).collection("templates").document(
        template_id).get()
    json_dict = doc.to_dict()["workflowProcessor"]

    csv = json_dict["write"]["spreadsheet"]["csv"]

    result = workflow_export(json_dict["write"], input_data,
                             csv)

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
    return result


def read_workflow_one(company_id, work_id, template_id, costs_dict, document_id, user_id, row_col_map):
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

    doc = db.collection("companies_tmp_completed").document(company_id).collection(
        "works").document(work_id).collection("read_workflow").document(document_id).get()
    if doc.exists:
        print("[for read_workflow_one] recovering from tmp_completed for " + document_id)
        doc_dict = doc.to_dict()
        tmp_dict = json.loads(doc_dict["tmp_dict"])
        export_dict = json.loads(doc_dict["export_dict"])
        if tmp_dict is None:
            tmp_dict = {}
    else:
        raise Exception("tmp_dict not found")

    csv = json_dict["write"]["spreadsheet"]["csv"]
    raw_map = dict()
    result = workflow_export(json_dict["write"], export_dict,
                             csv, raw_map)
    print(raw_map)

    target_keys = []
    replacing_key_values = dict()

    # { "key": "val" }
    for row_col in row_col_map:
        if row_col not in raw_map or row_col + "_raw" not in raw_map:
            raise Exception("target row not found")
        replacing_key_values[raw_map[row_col]] = row_col_map[row_col]
        target_keys.append(raw_map[row_col + "_raw"])

    started = False

    for reader in readers_page_zero:
        if not started:
            # find target_key from reader
            for key in reader:
                # forward
                if reader[key] in target_keys:
                    started = True
                    break
                # reverse
                for target_key in target_keys:
                    if target_key in str(reader[key]):
                        started = True
                        break
                if started:
                    break
        if not started:
            continue

        # replace key with value always
        for key in replacing_key_values:
            export_dict[key] = replacing_key_values[key]
        try:
            # in the api, you should read file from gcs
            if reader["provider"] == "openai-gpt" or reader["provider"] == "openai-gpt3":
                prompt_id = reader["base_prompt"]
                # get value from firestore, path: settings/private/prompt/{prompt_id}
                doc = db.collection("settings").document(
                    "private").collection("prompt").document(prompt_id).get()
                prompt = doc.to_dict()["prompt"]
                reader["base_prompt"] = prompt
            elif reader["provider"] == "clova-general":
                continue
            elif reader["provider"] == "refine":
                continue
            elif reader["provider"] == "clova-rect":
                continue
            elif reader["provider"] == "map":
                csv_file_bucket_path, data_str = load_master_csv_data(
                    reader, db, company_id)

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
                    data_bytes = bucket.blob(
                        bucket_file_path).download_as_string()
                    # bytes to string
                    data_str = data_bytes.decode("utf-8")
                    reader["vectors_data"] = json.loads(data_str)
        except:
            raise Exception(traceback.format_exc())
        try:
            workflow_read(reader, None, export_dict,
                          on_memory_dict, tmp_dict, costs_dict, user_id)
        except Exception as e:
            raise e

    def escape_replacing_key(key):
        special_key = key
        special_key = special_key.replace("{", "$$(")
        special_key = special_key.replace("}", "$$)")
        special_key = "%%(" + special_key + ")%%"
        return special_key

    """
    for key in replacing_key_values:
        export_dict[key] = escape_replacing_key(key)
    """

    csv = json_dict["write"]["spreadsheet"]["csv"]
    result = workflow_export(json_dict["write"], export_dict,
                             csv)

    # check required
    if "required_column" in json_dict["write"] and json_dict["write"]["required_column"] != "":
        try:
            # get header index
            header_index = result[0].index(
                json_dict["write"]["required_column"])
            if header_index >= 0:
                new_result = []
                new_result.append(result[0])
                for row in result[1:]:
                    if row[header_index] != "":
                        new_result.append(row)
                result = new_result
        except:
            pass

    return result


def check_limit():
    # get ope/counter firestore
    ope_counter = firestore.client().collection("ope").document("counter")
    # get max number
    max_number = ope_counter.get().to_dict()["max"]
    # get current number
    current_number = ope_counter.get().to_dict()["current"]

    # check current number is less than max number
    if current_number < max_number:
        # increment current number
        ope_counter.update({"current": current_number + 1})
        return True
    else:
        return False


def fail_by_limit():
    # return error
    return ("Error: Max number is reached.", 200, Cors.cors_headers())


def operate_uploaded_data(company_id, work_id, document_id, throw=False):
    # company
    company = firestore.client().collection("companies_userdata").document(
        company_id).get()
    # work
    work = firestore.client().collection("companies_userdata").document(
        company_id).collection("works").document(work_id).get()
    # document
    uploaded = firestore.client().collection("companies_userdata").document(
        company_id).collection("works").document(work_id).collection("uploaded").document(document_id).get()
    uploaded_dict = uploaded.to_dict()

    if uploaded_dict["uploadingStatus"] == "detected":
        # check limit if uploadingStatus is detected
        if not check_limit():
            raise PolarReadRetriableException("Max number is reached.")
    try:
        # to dict
        print("called with company_id: " + company_id +
              ", work_id: " + work_id + ", document_id: " + document_id)
        print(uploaded_dict)
        if uploaded_dict["uploadingStatus"] == "uploaded":
            print("Extracting...")
            if uploaded_dict["name"].lower().endswith(".pdf"):
                print("Pdf")
                # get file from storage
                bucket = storage.bucket()
                bucket_file_path = uploaded_dict["rawFilePath"]
                # get binary from file
                binary = bucket.blob(
                    bucket_file_path).download_as_string()

                # convert to image
                try:
                    mats = pdf2imgs(binary)
                except:
                    # never recoverable. set document with merge
                    uploaded.reference.set(
                        {"uploadingStatus": "failed", "uploadingError": "Failed to convert pdf to image."}, merge=True)
                    return ("Error: Failed to convert pdf to image.", 200, Cors.cors_headers())

                created_dicts = []

                # duplicate uploaded document for each image
                # only supports 1 page for each currently.
                i = 0
                for mat in mats:
                    # upload to bucket
                    path = uploaded_dict["rawFilePath"].replace(
                        "/user-files/", "/converted-files/") + "_" + str(i) + ".png"
                    # mat to file object
                    _, png_image = cv2.imencode(".png", mat)
                    file_object = io.BytesIO(png_image)
                    # upload to bucket
                    bucket.blob(path).upload_from_file(
                        file_object, content_type="image/png")
                    # create new uploaded document
                    uploaded_current_dict = uploaded_dict.copy()
                    uploaded_current_dict["convertedFilePaths"] = [
                        path]
                    uploaded_current_dict["imageIndexFrom"] = i
                    uploaded_current_dict["imageIndexTo"] = i
                    uploaded_current_dict["uploadingStatus"] = "extracted"
                    uploaded_current_dict["updatedAt"] = firestore.SERVER_TIMESTAMP
                    created_dicts.append(uploaded_current_dict)
                    i += 1

                # delete original uploaded document
                uploaded.reference.delete()

                # create new uploaded documents in 'uploaded' collection
                uploaded_datas = work.reference.collection(
                    "uploaded")
                for created_dict in created_dicts:
                    uploaded_datas.add(created_dict)

                # end processing
                return ("1", 200, Cors.cors_headers())
            else:
                print("Image")
                # assume it's image
                # get file from storage
                bucket = storage.bucket()
                bucket_file_path = uploaded_dict["rawFilePath"]
                # get binary from file
                binary = bucket.blob(
                    bucket_file_path).download_as_string()
                # convert to image
                mat = cv2.imdecode(np.fromstring(
                    binary, np.uint8), cv2.IMREAD_COLOR)
                # upload opencv mat to bucket
                path = uploaded_dict["rawFilePath"].replace(
                    "/user-files/", "/converted-files/") + ".png"
                # mat to file object
                _, png_image = cv2.imencode(".png", mat)
                file_object = io.BytesIO(png_image)
                # upload to bucket
                bucket.blob(path).upload_from_file(
                    file_object, content_type="image/png")
                uploaded_dict["convertedFilePaths"] = [path]
                uploaded_dict["uploadingStatus"] = "extracted"
                uploaded_dict["updatedAt"] = firestore.SERVER_TIMESTAMP
                # update
                uploaded.reference.set(uploaded_dict)
                # end processing
                return ("1", 200, Cors.cors_headers())
        elif uploaded_dict["uploadingStatus"] == "extracted":
            # =====================
            # detect angle
            print("Detect pre-angle...")
            time_detect_start = time.time()

            bucket = storage.bucket()
            bucket_file_path = uploaded_dict["convertedFilePaths"][0]
            binary = bucket.blob(bucket_file_path).download_as_string()

            time_download = time.time()
            print("Download time: " + str(time_download - time_detect_start))

            mat = cv2.imdecode(np.fromstring(
                binary, np.uint8), cv2.IMREAD_COLOR)

            time_imdecode = time.time()
            print("Imdecode time: " + str(time_imdecode - time_download))

            angle = detect_get_angle_only(mat)

            time_angle = time.time()
            print("Angle time: " + str(time_angle - time_imdecode))

            uploaded_dict["uploadingStatus"] = "detected"
            uploaded_dict["updatedAt"] = firestore.SERVER_TIMESTAMP
            uploaded_dict["convertedFileAngles"] = [angle]
            # update uploaded document
            uploaded.reference.set(uploaded_dict)

            time_finish = time.time()
            print("Finish time: " + str(time_finish - time_angle))
            # end processing
            return ("1", 200, Cors.cors_headers())
        elif uploaded_dict["uploadingStatus"] == "detected":
            # =====================
            # convert
            print("Detect angle...")
            bucket = storage.bucket()
            bucket_file_path = uploaded_dict["convertedFilePaths"][0]
            angle = uploaded_dict["convertedFileAngles"][0]
            if "imageIndexFrom" in uploaded_dict:
                image_index = uploaded_dict["imageIndexFrom"]
            else:
                image_index = 0
            binary = bucket.blob(bucket_file_path).download_as_string()
            mat = cv2.imdecode(np.fromstring(
                binary, np.uint8), cv2.IMREAD_COLOR)
            mat, text_angle, text_angle_x = detect_with_angles(mat, angle)
            uploaded_dict["textAngles"] = [text_angle]
            uploaded_dict["textAngleXs"] = [text_angle_x]
            # upload to bucket
            path = uploaded_dict["rawFilePath"].replace(
                "/user-files/", "/converted-files/") + "_" + str(image_index) + ".png"
            # mat to file object
            _, png_image = cv2.imencode(".png", mat)
            file_object = io.BytesIO(png_image)
            # upload to bucket
            bucket.blob(path).upload_from_file(
                file_object, content_type="image/png")
            uploaded_dict["uploadingStatus"] = "converted"
            # delete original uploaded document
            uploaded.reference.delete()
            # create new uploaded document in 'converted' collection
            converted_datas = work.reference.collection(
                "converted")
            uploaded_dict["status"] = "converted"
            uploaded_dict["updatedAt"] = firestore.SERVER_TIMESTAMP
            converted_datas.document(
                uploaded.id).set(uploaded_dict)
            # end processing
            return ("1", 200, Cors.cors_headers())
    except Exception as e:
        import traceback
        traceback.print_exc()
        if throw:
            raise e
        # end processing
        return ("0", 200, Cors.cors_headers())
    finally:
        pass


def operate_converted_data(company_id, work_id, document_id):
    # company
    company = firestore.client().collection("companies_userdata").document(
        company_id).get()
    # work
    work = firestore.client().collection("companies_userdata").document(
        company_id).collection("works").document(work_id).get()
    # document
    converted = firestore.client().collection("companies_userdata").document(
        company_id).collection("works").document(work_id).collection("converted").document(document_id).get()
    if not check_limit():
        raise PolarReadRetriableException("Max number is reached.")
    try:
        # to dict
        converted_dict = converted.to_dict()
        uid = ""
        if "createdBy" in converted_dict:
            uid = converted_dict["createdBy"]
            print("UID is " + uid)
        # get file from storage
        bucket = storage.bucket()
        bucket_file_path = converted_dict["convertedFilePaths"][0]
        # get binary from file
        binary = bucket.blob(bucket_file_path).download_as_string()
        # convert to image
        mat = cv2.imdecode(np.fromstring(
            binary, np.uint8), cv2.IMREAD_COLOR)
        from recog_utils import match_template, read_workflow, write_workflow
        print("working on: " + converted.id)
        if "templateId" in converted_dict:
            print("templateId found")
            template_id = converted_dict["templateId"]
        else:
            template_id, similarity = match_template(
                mat, company.id, work.id, False)
            converted_dict["templateId"] = template_id
            converted_dict["templateSimilarity"] = similarity
            # update
            converted.reference.set(converted_dict)
        if template_id == "":
            print("failed to find template")
            # create inner data
            inner_data = work.reference.collection("inner_data")
            inner_data.document(converted.id).set({
                "createdAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            })
            converted_dict["isFailed"] = True
            converted_dict["status"] = "failed"
            converted_dict["updatedAt"] = firestore.SERVER_TIMESTAMP
            # move converted to failed
            failed_datas = work.reference.collection("failed")
            failed_datas.document(converted.id).set(converted_dict)
            converted.reference.delete()
            return ("1", 200, Cors.cors_headers())
        print("found template: " + template_id)
        # if this process failed, we can retry so there is no try-catch (currently. we need alternative way)
        # but its in beta. we catches all
        costs_dict = dict()
        try:
            print("reading...")
            read_data = read_workflow(
                mat, company.id, work.id, template_id, False, costs_dict, document_id, uid)
            print("writing...")

            # NOTE: Generate OutPut File Name Process
            company_work_template_document = firestore.client().collection(
                "companies").document(company_id).collection("works").document(work_id).collection(
                "templates").document(
                template_id).get().to_dict()

            output_file_name = ""
            if 'expectOutPutFileName' in company_work_template_document:
                print("!find expected output file name")

                expect_out_put_file_name = company_work_template_document[
                    'expectOutPutFileName']  # NOTE: ex.) 猫-{general.text.test}-{general.text.1}
                expect_workflow_predict_convert_out_put_file_name_list = re.findall(r'{(.*?)}',
                                                                                    expect_out_put_file_name)
                for expect_workflow_predict_convert_out_put_file_name in expect_workflow_predict_convert_out_put_file_name_list:
                    if expect_workflow_predict_convert_out_put_file_name in read_data:
                        search_expect_workflow_predict_convert_out_put_file_name = "{" + expect_workflow_predict_convert_out_put_file_name + "}"
                        expect_out_put_file_name = expect_out_put_file_name.replace(
                            search_expect_workflow_predict_convert_out_put_file_name,
                            read_data[expect_workflow_predict_convert_out_put_file_name])
                output_file_name = expect_out_put_file_name
            else:
                print("not find expected output file name")

            wrote = write_workflow(
                company.id, work.id, template_id, read_data)
            # remove header
            header = wrote[0]
            wrote = wrote[1:]
            csv_text = table_to_csv_text(wrote).strip()
            header_text = table_to_csv_text([header]).strip()
            # calc non-empty cells
            try:
                cells = 0
                for row in wrote:
                    for cell in row:
                        if cell != None and cell != "" and cell.strip() != "" and cell.strip().strip(
                                "\"").strip() != "":
                            cells += 1
                costs_dict["cells"] = cells
            except:
                costs_dict["cells"] = 0
                pass
        except PolarReadRetriableException as e:
            # retriable. we can retry
            print("failed to read or write but retriable")
            raise e
            return ("0", 400, cors_headers())
        except Exception as e:
            print(e)
            print("failed to read or write")
            # create inner data
            inner_data = work.reference.collection("inner_data")
            inner_data.document(converted.id).set({
                "createdAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
                "templateId": template_id,
            })
            converted_dict["isFailed"] = True
            converted_dict["isProcessingFailed"] = True
            converted_dict["status"] = "failed"
            converted_dict["updatedAt"] = firestore.SERVER_TIMESTAMP
            # move converted to failed
            failed_datas = work.reference.collection("failed")
            failed_datas.document(converted.id).set(converted_dict)
            converted.reference.delete()
            return ("1", 200, Cors.cors_headers())

        # create inner data
        inner_data = work.reference.collection("inner_data")
        inner_data.document(converted.id).set({
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
            "expectedBody": csv_text,
            "header": header_text,
            "actualBody": csv_text,
            "templateId": template_id,
            "costs": costs_dict,
            "outputFileName": output_file_name,
        })
        converted_dict["isFailed"] = False
        converted_dict["isProcessingFailed"] = False
        converted_dict["status"] = "succeeded"
        converted_dict["updatedAt"] = firestore.SERVER_TIMESTAMP
        # move converted to succeeded
        succeeded_datas = work.reference.collection("succeeded")
        succeeded_datas.document(converted.id).set(converted_dict)
        converted.reference.delete()
        # create costs data
        try:
            firestore.client().collection("companies_cost").document(company_id).collection("works").document(
                work_id).collection("succeeded").document(converted.id).set({
                "createdAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
                "costs": costs_dict,
            })
        except:
            pass
        # end processing
        return ("1", 200, Cors.cors_headers())
    except Exception as e:
        # end processing
        raise e
        return ("0", 200, cors_headers())
    finally:
        pass
