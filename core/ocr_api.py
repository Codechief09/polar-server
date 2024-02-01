import threading
import time
import traceback
import google.cloud.aiplatform as aip
import statistics
import cv2
from variables import get_gcp_project_id, get_gcp_location, get_vertex_ocr_endpoint_name_prefix

endpoint = None
crop_height_threshold = 0.1
crop_width_threshold = 0.2
resize_threshold = 2400


def init_if_endpoint_is_not_initialized():
    global endpoint
    if endpoint is not None:
        return
    try:
        # init
        print("target project: " + get_gcp_project_id())
        aip.init(project=get_gcp_project_id(), location=get_gcp_location())

        # retrieve endpoints
        endpoints = aip.Endpoint.list()
        # filter endpoints by display_name starting with var
        endpoints = list(
            filter(lambda x: x.display_name.startswith(get_vertex_ocr_endpoint_name_prefix()), endpoints))
        endpoint = endpoints[-1]
    except:
        print("failed to initialize endpoint")
        traceback.print_exc()


init_if_endpoint_is_not_initialized()


def cheap_trick_to_assume_is_image_has_object(cropped_image):
    img = cropped_image
    # crop from top and bottom, from left and right
    height, width = img.shape[:2]
    img = img[int(height * crop_height_threshold):int(height * (1.0 - crop_height_threshold)),
              int(width * crop_width_threshold):int(width * (1.0 - crop_width_threshold))]
    # draw outer frame with white with 5px
    img = cv2.copyMakeBorder(img, 5, 5, 5, 5,
                             cv2.BORDER_CONSTANT, value=(255, 255, 255))
    # convert to gray scale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # remove noise
    blur = cv2.GaussianBlur(gray, (9, 9), 0)
    # binarize
    ret, th = cv2.threshold(blur, 127, 255, cv2.THRESH_BINARY_INV)
    # find contours
    contours, _ = cv2.findContours(
        th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # check
    found = False
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w < 2 or h < 20:
            continue
        found = True
    return found


def predict(cv_image, xywh, result, result_idx):
    result[result_idx] = ""
    cropped_image = cv_image[xywh[1]:xywh[1] +
                             xywh[3], xywh[0]:xywh[0] + xywh[2]]
    # save to tmp/
    # cv2.imwrite("tmp/" + str(result_idx) + ".jpg", cropped_image)
    cheap_trick_result = cheap_trick_to_assume_is_image_has_object(
        cropped_image)
    if not cheap_trick_result:
        return
    # predict
    res = endpoint.raw_predict(
        body=cv2.imencode('.jpg', cropped_image)[1].tobytes(),
        headers={
            "Content-Type": "image/jpeg",
        }
    )
    if res.status_code != 200:
        result[result_idx] = "!ERROR!"
        return
    parsed = res.json()
    if parsed != None and len(parsed) != 0 and parsed[0] != None:
        result[result_idx] = parsed[0]


def predicts(_cv_image, cropVerticesArray):
    init_if_endpoint_is_not_initialized()
    cv_image = _cv_image.copy()
    print("starting predicts...")
    start_time = time.time()
    enableThreading = False
    # 0. resize image scale close to reisze_threshold
    shape = cv_image.shape
    scale = 1.0
    smaller = min(shape[0], shape[1])
    if smaller < resize_threshold:
        scale = resize_threshold / smaller
        cv_image = cv2.resize(
            cv_image, (int(shape[1] * scale), int(shape[0] * scale)))
    elif smaller > resize_threshold:
        scale = smaller / resize_threshold
        cv_image = cv2.resize(
            cv_image, (int(shape[1] / scale), int(shape[0] / scale)))
    # 1. convert vertices
    # convert cropVerticesArray to (x, y, w, h)
    converted = []
    for cropVertices in cropVerticesArray:
        x = int(cropVertices[0]["x"] * cv_image.shape[1])
        y = int(cropVertices[0]["y"] * cv_image.shape[0])
        w = int(cropVertices[1]["x"] * cv_image.shape[1]) - x
        h = int(cropVertices[2]["y"] * cv_image.shape[0]) - y
        converted.append([x, y, w, h])
    # 2. align width
    # now, we assume all of converted width should be very similar
    # but in some cases, it's not. so we try to make it similar if too small data is detected
    # first of all, we calculate median of width
    median = statistics.median([x[2] for x in converted])
    # then, we check if there is too small data
    for i in range(len(converted)):
        if converted[i][2] < median * 0.8:
            # too small data detected
            # we try to make it similar
            converted[i][2] = int(median)
    # predict
    results = [""] * len(converted)
    if enableThreading:
        # predict by threading
        # grouped by up to 3
        grouped = []
        threads_cnt = 5
        for i in range(0, len(converted), threads_cnt):
            grouped.append(converted[i:i + threads_cnt])
        results = []
        for group in grouped:
            threads = []
            threads_result = [""] * len(group)
            i = -1
            for cropVertices in group:
                i += 1
                threads.append(threading.Thread(
                    target=predict, args=(cv_image, cropVertices, threads_result, i)))
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            for result in threads_result:
                if result is None:
                    raise Exception("failed to predict")
                results.append(result)
        print("finished predicts...")
        print("elapsed: " + str(time.time() - start_time) + "s")
        return results
    else:
        # predict by for loop
        for i in range(len(converted)):
            predict(cv_image, converted[i], results, i)
            if results[i] is None:
                raise Exception("failed to predict")
        print("finished predicts...")
        print("elapsed: " + str(time.time() - start_time) + "s")
        return results
