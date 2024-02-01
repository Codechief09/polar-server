from core.clova_ext import parse_general_tables_into_arrays, tables_to_csv_text, parse_general_data_into_text_by_line
from core.clova import general
import cv2

# read image
image = cv2.imread("batton_test.png")

# clova general
clova_result = general(image, True)

# parse tables
tables = parse_general_tables_into_arrays(clova_result)

# print tables
print(tables_to_csv_text(tables))

# print text without table
print(parse_general_data_into_text_by_line(clova_result, True))
