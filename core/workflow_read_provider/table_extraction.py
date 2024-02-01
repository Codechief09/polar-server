from core.clova_table_prettier import pretty_cells
from core.clova_table_matcher import extract_table, put_extracted_table_to_dict


def table_extract_strategy_pretty(read_id, tmp_dict, req_dict, export_dict, var_to_rect_fn):
    clova_result = tmp_dict["clova_general"]
    tables = []

    convertedWidth = clova_result["images"][0]["convertedImageInfo"]["width"]
    convertedHeight = clova_result["images"][0]["convertedImageInfo"]["height"]

    expected_header_str = req_dict["expectedHeader"]
    mapper_str = req_dict["mapper"]

    expected_header = []
    for col in expected_header_str.split(","):
        expected_header.append(col)

    mapper = []
    for col in mapper_str.split(","):
        mapper.append(col)

    table_display_idx = 0
    for table_idx in range(len(clova_result["images"][0]["tables"])):
        cells, image = pretty_cells(clova_result, table_idx, False, None)
        table = extract_table(cells, expected_header, [])
        if table == None:
            continue
        put_extracted_table_to_dict(
            table, convertedWidth, convertedHeight, table_display_idx, mapper, read_id, export_dict, var_to_rect_fn)
        table_display_idx += 1
