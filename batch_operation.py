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

import firebase_initializer
from core.clova import general
from core.clova_ext import table_to_csv_text
from core.document_similarity import check_document_similarity
from core.gpt import completion
from core.gpt_ext import create_embeddings_from_csv
from core.pdf2img import pdf2img, pdf2imgs
from core.skew_detection import detect
from core.workflow_export import workflow_export
from core.workflow_read import workflow_read
from js_utils import unify_alphas, unify_numbers, unify_symbols
from recog_utils import operate_converted_data, operate_uploaded_data
from utils import verified_uid


@firestore.transactional
def _acquire_document(transaction, target, company_id, work_id, document_id):
    # get processing collection with transaction
    processing = firestore.client().collection("processing")
    # create document if not exists with transaction
    # if exists, raise exception
    res = transaction.create(processing.document(target), {
        "company_id": company_id,
        "work_id": work_id,
        "document_id": document_id,
        # firestore timestamp
        "created_at": firestore.SERVER_TIMESTAMP,
    })


def acquire_document(company_id, work_id, document_id):
    target = company_id + "-" + work_id + "-" + document_id
    print("trying to acquire: " + target)
    try:
        # create transaction
        transaction = firestore.client().transaction()
        _acquire_document(transaction, target, company_id,
                          work_id, document_id)
        print("acquired: " + target)
        return True
    except:
        import traceback
        traceback.print_exc()
        print("conflicted: " + target)
        return False


@firestore.transactional
def _release_document(transaction, target):
    # get processing collection with transaction
    processing = firestore.client().collection("processing")
    # delete document with transaction
    print(target)
    transaction.delete(processing.document(target))


def release_document(company_id, work_id, document_id):
    target = company_id + "-" + work_id + "-" + document_id
    print("trying to release: " + target)
    try:
        # create transaction
        transaction = firestore.client().transaction()
        _release_document(transaction, target)
        print("released: " + target)
        return True
    except:
        import traceback
        traceback.print_exc()
        print("failed to release: " + target)
        return False


def update_uploaded_as_detected_system_last_updated_at():
    try:
        # update last_updated_at
        print("updating...")
        firestore.client().collection("ope").document("uploaded_update_to_detected").set({
            "last_updated_at": firestore.SERVER_TIMESTAMP,
        })
        print("done...")
    except:
        import traceback
        traceback.print_exc()
        # we can fail anytime
        pass


def update_converted_system_last_updated_at():
    try:
        # ope/updates
        document = firestore.client().collection("ope").document("converted_add").get()
        # update last_updated_at
        firestore.client().collection("ope").document("converted_add").set({
            "last_updated_at": firestore.SERVER_TIMESTAMP,
        })
    except:
        # we can fail anytime
        pass


"""
target_status should be one of `uploaded`, `extracted`
"""


def deal_uploaded_data_preprocess(company_id, work_id, document_id, target_uploading_status):
    # get document
    document = firestore.client().collection("companies_userdata").document(company_id).collection(
        "works").document(work_id).collection("uploaded").document(document_id).get()
    if not document.exists:
        print("200 document not found: " + company_id +
              "/" + work_id + "/" + document_id)
        return True
    # check if uploadingStatus is `uploaded` or `extracted`
    if document.to_dict()["uploadingStatus"] != target_uploading_status:
        # it indicates that the document is already processed
        # so just return True
        print("200 document status [" + document.to_dict()["uploadingStatus"] + "] is not " +
              target_uploading_status + ": " + company_id + "/" + work_id + "/" + document_id)
        return True
    # acquire lock with document_id} in `processing` collection with transaction
    if acquire_document(company_id, work_id, document_id) == False:
        print("400 failed to acquire: " + company_id +
              "/" + work_id + "/" + document_id)
        return False
    try:
        operate_uploaded_data(company_id, work_id, document_id)
        # update system last updated at for watching document changes
        if target_uploading_status == "extracted":
            # if target uploading status is extracted, its now detected. so update detected system last updated at
            update_uploaded_as_detected_system_last_updated_at()
    except:
        import traceback
        traceback.print_exc()
        print("400 failed to operate: " + company_id +
              "/" + work_id + "/" + document_id)
        return False
    finally:
        release_document(company_id, work_id, document_id)
    print("200 success: " + company_id + "/" + work_id + "/" +
          document_id + " with " + target_uploading_status)
    return True


"""
Randomly select a company, work, and uploaded data
"""


def deal_uploaded_data_random(target_uploading_status):
    # list companies_userdata
    companies_userdata = firestore.client().collection("companies_userdata")

    # get last company from ope/last_company
    last_company = firestore.client().collection(
        "ope").document("last_company").get()
    # exists
    if not last_company.exists:
        # create
        firestore.client().collection("ope").document("last_company").set({
            "id": ""
        })
        last_company = firestore.client().collection(
            "ope").document("last_company").get()

    last_company_id = last_company.to_dict()["id"]

    # get all companies
    companies = []
    for company in companies_userdata.stream():
        if company.id != last_company_id:
            companies.append(company.id)

    # shuffle
    random.shuffle(companies)

    # set last_company_id as last one
    if last_company_id != "":
        companies.append(last_company_id)

    for company_id in companies:
        # list works
        works = companies_userdata.document(company_id).collection("works")
        works_array = []
        for work in works.stream():
            works_array.append(work)
        random.shuffle(works_array)
        for work in works_array:
            # get a document from uploaded subcollection where status is `uploaded`
            uploaded_list = list(work.reference.collection("uploaded").where(
                "uploadingStatus", "==", target_uploading_status).limit(5).stream())
            # check len
            if len(uploaded_list) == 0:
                continue
            # get first
            for uploaded in uploaded_list:
                # acquire lock with document_id} in `processing` collection with transaction
                if acquire_document(company_id, work.id, uploaded.id) == False:
                    continue
                try:
                    # set last company
                    firestore.client().collection("ope").document("last_company").set({
                        "id": company_id
                    })
                    operate_uploaded_data(
                        company_id, work.id, uploaded.id, True)
                    if target_uploading_status == "detected":
                        # if target uploading status is detected, its now converted state.
                        update_converted_system_last_updated_at()
                    return 1, "", None
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    return 1, "with-error", e
                finally:
                    release_document(company_id, work.id, uploaded.id)
    return 0, "", None


"""
Randomly select a company, work, and uploaded data
"""


def deal_converted_data_random():
    # list companies_userdata
    companies_userdata = firestore.client().collection("companies_userdata")

    # get last company from ope/last_company
    last_company = firestore.client().collection(
        "ope").document("last_company").get()
    # exists
    if not last_company.exists:
        # create
        firestore.client().collection("ope").document("last_company").set({
            "id": ""
        })
        last_company = firestore.client().collection(
            "ope").document("last_company").get()

    last_company_id = last_company.to_dict()["id"]

    # get all companies
    companies = []
    for company in companies_userdata.stream():
        if company.id != last_company_id:
            companies.append(company.id)

    # shuffle
    random.shuffle(companies)

    # set last_company_id as last one
    if last_company_id != "":
        companies.append(last_company_id)

    for company_id in companies:
        # list works
        works = companies_userdata.document(company_id).collection("works")
        works_array = []
        for work in works.stream():
            works_array.append(work)
        random.shuffle(works_array)
        for work in works_array:
            # get a document from uploaded subcollection where status is `uploaded`
            converted_list = list(work.reference.collection(
                "converted").limit(5).stream())
            # check len
            if len(converted_list) == 0:
                continue
            # get first
            for converted in converted_list:
                # acquire lock with document_id} in `processing` collection with transaction
                if acquire_document(company_id, work.id, converted.id) == False:
                    continue
                try:
                    # set last company
                    firestore.client().collection("ope").document("last_company").set({
                        "id": company_id
                    })
                    operate_converted_data(company_id, work.id, converted.id)
                    return 1, "", None
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    return 1, "with-error", e
                finally:
                    release_document(company_id, work.id, converted.id)
    return 0, "", None
