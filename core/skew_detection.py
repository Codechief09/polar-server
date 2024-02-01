from jdeskew.estimator import get_angle
import cv2
import imutils
from core.clova import general
from PIL import Image
import numpy as np
import re


def cv2pil(image):
    ''' OpenCV型 -> PIL型 '''
    new_image = image.copy()
    if new_image.ndim == 2:  # モノクロ
        pass
    elif new_image.shape[2] == 3:  # カラー
        new_image = cv2.cvtColor(new_image, cv2.COLOR_BGR2RGB)
    elif new_image.shape[2] == 4:  # 透過
        new_image = cv2.cvtColor(new_image, cv2.COLOR_BGRA2RGBA)
    new_image = Image.fromarray(new_image)
    return new_image


def pil2cv(image):
    ''' PIL型 -> OpenCV型 '''
    new_image = np.array(image, dtype=np.uint8)
    if new_image.ndim == 2:  # モノクロ
        pass
    elif new_image.shape[2] == 3:  # カラー
        new_image = cv2.cvtColor(new_image, cv2.COLOR_RGB2BGR)
    elif new_image.shape[2] == 4:  # 透過
        new_image = cv2.cvtColor(new_image, cv2.COLOR_RGBA2BGRA)
    return new_image


def isascii(s):
    asciiReg = re.compile(r'^[!-~]+$')
    return asciiReg.match(s) is not None


def clova_flip_detection(image):
    response_json = general(image, False)
    # check how vertices.y increments (plus or minus)
    plus_count = 0
    minus_count = 0
    inferConfidenceThreshold = 0.9
    # phase 1. inferText should be japaneseText and confidence should be large
    while (plus_count < 2 and minus_count < 2) and inferConfidenceThreshold > 0.5:
        plus_count = 0
        minus_count = 0
        inferConfidenceThreshold -= 0.05
        for field in response_json['images'][0]['fields']:
            if len(field['inferText']) < 2 or isascii(field["inferText"]) or field["inferConfidence"] < inferConfidenceThreshold:
                continue
            boundingPoly = field['boundingPoly']
            if boundingPoly['vertices'][0]['y'] < boundingPoly['vertices'][2]['y']:
                plus_count += 1
            else:
                minus_count += 1
    # phase 2. confidence based
    inferConfidenceThreshold = 0.9
    while (plus_count < 2 and minus_count < 2) and inferConfidenceThreshold > 0.5:
        plus_count = 0
        minus_count = 0
        inferConfidenceThreshold -= 0.05
        for field in response_json['images'][0]['fields']:
            if len(field['inferText']) < 2 or field["inferConfidence"] < inferConfidenceThreshold:
                continue
            boundingPoly = field['boundingPoly']
            if boundingPoly['vertices'][0]['y'] < boundingPoly['vertices'][2]['y']:
                plus_count += 1
            else:
                minus_count += 1
    print(str(plus_count) + " > " + str(minus_count))
    rotation_for_y = 0
    if plus_count > minus_count:
        rotation_for_y = 0
    else:
        rotation_for_y = 180
    return rotation_for_y


def clova_flip_detection_x(image):
    response_json = general(image, False)
    # check how vertices.x increments (plus or minus)
    plus_count = 0
    minus_count = 0
    normal_count = 0
    inferConfidenceThreshold = 0.9
    # phase 1. inferText should be japaneseText and confidence should be large
    while (plus_count < 2 and minus_count < 2 and normal_count < 5) and inferConfidenceThreshold > 0.5:
        plus_count = 0
        minus_count = 0
        normal_count = 0
        inferConfidenceThreshold -= 0.05
        for field in response_json['images'][0]['fields']:
            if len(field['inferText']) < 2 or isascii(field["inferText"]) or field["inferConfidence"] < inferConfidenceThreshold:
                continue
            boundingPoly = field['boundingPoly']
            if boundingPoly['vertices'][0]['x'] < boundingPoly['vertices'][1]['x'] and abs(boundingPoly["vertices"][0]["x"] - boundingPoly["vertices"][1]["x"]) > 10:
                normal_count += 1
            if boundingPoly['vertices'][0]['x'] < boundingPoly['vertices'][3]['x'] and abs(boundingPoly["vertices"][0]["x"] - boundingPoly["vertices"][3]["x"]) > 10:
                plus_count += 1
            elif boundingPoly['vertices'][0]['x'] > boundingPoly['vertices'][3]['x'] and abs(boundingPoly["vertices"][0]["x"] - boundingPoly["vertices"][3]["x"]) > 10:
                minus_count += 1
    print("normal: " + str(normal_count))
    print("x: " + str(plus_count) + " > " + str(minus_count))
    rotation_for_x = 0
    if normal_count < 5 or (normal_count < 8 and (plus_count >= 5 or minus_count >= 5)):
        if (plus_count >= 2 or minus_count >= 2):
            if plus_count > minus_count:
                rotation_for_x = -90
            else:
                rotation_for_x = 90
    return rotation_for_x


def rotate_image(image, angle, color):
    # use PIL to have better rotation
    pilImage = cv2pil(image).rotate(
        angle, resample=Image.Resampling.BICUBIC, expand=True)
    return pil2cv(pilImage)


def detect_get_angle_only(image):
    base_image = image
    # Get angle
    # height more than 2000
    # height more than 2000
    if image.shape[0] > 2000:
        print("height shaped")
        image_resized = imutils.resize(image, height=2000)
        angle = get_angle(image_resized, angle_max=95)
    # width more than 2000
    elif image.shape[1] > 2000:
        print("width shaped")
        image_resized = imutils.resize(image, width=2000)
        angle = get_angle(image_resized, angle_max=95)
    else:
        angle = get_angle(image, angle_max=95)
    return angle


def detect_with_angles(image, angle=None):
    base_image = image
    # Get angle
    # height more than 2000
    # height more than 2000
    if image.shape[0] > 2000:
        print("height shaped")
        image_resized = imutils.resize(image, height=2000)
        if angle == None:
            angle = get_angle(image_resized, angle_max=95)
    # width more than 2000
    elif image.shape[1] > 2000:
        print("width shaped")
        image_resized = imutils.resize(image, width=2000)
        if angle == None:
            angle = get_angle(image_resized, angle_max=95)
    else:
        if angle == None:
            angle = get_angle(image, angle_max=95)
    print(angle)

    # Rotate image
    image = rotate_image(image, angle, (255, 255, 255))

    # get text angle
    text_angle = clova_flip_detection(image)

    # Rotate image
    if text_angle != 0:
        # use base_image to get more quality than rotate image twice
        print("TEXT_ANGLE")
        image = rotate_image(image, text_angle, (255, 255, 255))

    # get text angle for x
    text_angle_x = clova_flip_detection_x(image)

    # Rotate image
    if text_angle_x != 0:
        print("TEXT_ANGLE_X")
        image = rotate_image(image, text_angle_x, (255, 255, 255))

    return image, text_angle, text_angle_x


def detect(image, angle=None):
    image, _, _ = detect_with_angles(image, angle)
    return image


def detect_image(filename):
    # Load image
    image = cv2.imread(filename)
    return detect(image)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python skew_detection.py <image>")
        sys.exit(1)
    image = detect_image(sys.argv[1])
    cv2.imshow("Rotated image", image)
    cv2.waitKey(0)
