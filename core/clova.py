import requests
import uuid
import time
import json
import cv2
from variables import get_clova_api_url, get_clova_secret_key, get_clova_infer_api_url, get_clova_infer_secret_key
from core.polar_exception import PolarReadNonRetriableException, PolarReadRetriableException


def general(cv_mat_image, enableTableDetection=True, shrinkThreshold=-1):
    print("general...")
    api_url = get_clova_api_url()
    secret_key = get_clova_secret_key()

    # resize image to 400px if size is smaller than 4000px width or height
    target_image = cv_mat_image
    if shrinkThreshold != -1:
        height, width, _ = cv_mat_image.shape
        threshold = shrinkThreshold
        if height > threshold or width > threshold:
            if width > height:
                target_image = cv2.resize(
                    cv_mat_image, (threshold, int(threshold * height / width)))
            else:
                target_image = cv2.resize(
                    cv_mat_image, (int(threshold * width / height), threshold))

    # save image
    # cv2.imwrite("test.png", target_image)
    # encode opencv image to jpg bytes
    _, jpg_image = cv2.imencode('.png', target_image)

    # request to clova server
    request_json = {
        'images': [
            {
                'format': 'png',
                'name': 'demo'
            }
        ],
        'requestId': str(uuid.uuid4()),
        'version': 'V2',
        'timestamp': int(round(time.time() * 1000)),
        'enableTableDetection': enableTableDetection,
    }

    payload = {'message': json.dumps(request_json).encode('UTF-8')}
    files = [
        ('file', jpg_image)
    ]
    headers = {
        'X-OCR-SECRET': secret_key
    }

    # retry
    succeeded = False
    for i in range(10):
        try:
            response = requests.request(
                "POST", api_url, headers=headers, data=payload, files=files)
        except:
            # retry if request failed
            time.sleep(2)
            continue
        if response.status_code == 200:
            succeeded = True
            break
        # get body
        response_json = json.loads(response.text.encode('utf8'))
        if ["0001", "0002", "0011", "0021", "0022", "1021"].count(response_json["code"]) > 0:
            # not continuable error. there is no need to retry
            raise PolarReadNonRetriableException(
                "clova apia request failed with code: {}".format(response_json["code"]))
        if i < 9:
            print("retrying...")
            time.sleep(2)

    if not succeeded:
        # retry failed but continuable error
        raise PolarReadRetriableException("clova api request failed")

    # get json
    response_json = json.loads(response.text.encode('utf8'))

    # check images.inferResult is "SUCCESS"
    if response_json['images'][0]['inferResult'] != 'SUCCESS':
        raise PolarReadNonRetriableException(
            'Error: {}'.format(response_json['images'][0]['inferResult']))

    return response_json


def infer(cv_mat_image, templateIds, api_url, secret_key):
    print("infer...")

    # encode opencv image to jpg bytes
    _, jpg_image = cv2.imencode('.png', cv_mat_image)

    # request to clova server
    request_json = {
        'images': [
            {
                'format': 'png',
                'name': 'demo',
                "templateIds": templateIds,
            }
        ],
        'requestId': str(uuid.uuid4()),
        'version': 'V2',
        'timestamp': int(round(time.time() * 1000)),
    }

    payload = {'message': json.dumps(request_json).encode('UTF-8')}
    files = [
        ('file', jpg_image)
    ]
    headers = {
        'X-OCR-SECRET': secret_key
    }

    # retry
    succeeded = False
    for i in range(10):
        try:
            response = requests.request(
                "POST", api_url, headers=headers, data=payload, files=files)
        except:
            # retry if request failed
            time.sleep(2)
            continue
        if response.status_code == 200:
            succeeded = True
            break
        # get body
        response_json = json.loads(response.text.encode('utf8'))
        if ["0001", "0002", "0011", "0021", "0022", "1021"].count(response_json["code"]) > 0:
            # not continuable error. there is no need to retry
            raise PolarReadNonRetriableException(
                "clova infer api request failed with code: {}".format(response_json["code"]))
        if i < 9:
            print("retrying...")
            time.sleep(2)

    if not succeeded:
        # retry failed but continuable error
        raise PolarReadRetriableException("clova infer api request failed")

    # get json
    response_json = json.loads(response.text.encode('utf8'))

    # check images.inferResult is "SUCCESS"
    if response_json['images'][0]['inferResult'] != 'SUCCESS':
        print(response_json)
        raise PolarReadNonRetriableException(
            'Error: {}'.format(response_json['images'][0]['inferResult']))

    return response_json
