import cv2
from core.clova_ext import parse_general_tables_into_arrays, tables_to_csv_text, parse_general_data_into_text_by_line
from core.clova import general
from core.document_similarity import check_document_similarity, reference2
from core.skew_detection import detect

# read image
image = cv2.imread("batton_test.png")

# image = detect(image)

# clova general
clova_result = general(image, False)

sim, comb = check_document_similarity(reference2, clova_result["images"][0]["fields"])
print(sim)
