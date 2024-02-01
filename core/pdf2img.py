import glob
import sys
import fitz
import numpy as np
import cv2
from pdf2image import convert_from_path, convert_from_bytes
from core.skew_detection import pil2cv
import imutils


"""
def pix2np(pix):
    im = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
    im = np.ascontiguousarray(im[..., [2, 1, 0]])  # rgb to bgr
    return im

def pdf2img(file):
    # To get better resolution
    zoom_x = 2.0  # horizontal zoom
    zoom_y = 2.0  # vertical zoom
    mat = fitz.Matrix(zoom_x, zoom_y)  # zoom factor 2 in each dimension
    with fitz.open(stream=file, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=mat)
            return pix2np(pix)
    return None
"""


def pdf2img(file):
    images = convert_from_bytes(file, dpi=300, fmt="png")
    if len(images) == 0:
        return None
    image = images[0]
    mat = pil2cv(image)
    return mat


def pdf2imgs(file):
    images = convert_from_bytes(file, dpi=300, fmt="png")
    if len(images) == 0:
        return None
    ret = []
    for image in images:
        ret.append(pil2cv(image))
    return ret
