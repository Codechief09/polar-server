from core.clova_ext import getTextFromCell
from core.clova_ext import convert_boundingPoly_to_ratio


def extract_simple(cells):
    table = []
    for row in cells:
        cols = []
        for col in row:
            cols.append({"text": getTextFromCell(col), "cell": col})
        table.append(cols)
    return table


def extract_simple_ignoring_empty_header(cells):
    table = extract_simple(cells)
    empty_idxs = []
    for idx, col in enumerate(table[0]):
        if col["text"] == "":
            empty_idxs.append(idx)
    # sort and reverse
    empty_idxs.sort()
    empty_idxs.reverse()
    # now remove
    for idx in empty_idxs:
        for row in table:
            del row[idx]
    return table


def strip_str(text):
    return text.replace(" ", "").replace("\n", "").replace("\t", "")


def extract_table_from_table_by_matching_header(table, expected_header):
    header = table[0]
    header_idx = []
    for idx, col in enumerate(header):
        if strip_str(col["text"]) in strip_str(expected_header):
            header_idx.append(idx)

    if len(header_idx) < len(expected_header):
        return None

    new_table = []
    for row in table:
        new_row = []
        for idx in header_idx:
            new_row.append(row[idx])
        new_table.append(new_row)
    return new_table


def extract_table_from_table_by_matching_header_contains(table, expected_header):
    header = table[0]
    header_idx = []
    for idx, col in enumerate(header):
        # find contains in expected_header
        for i in range(len(expected_header)):
            expected = expected_header[i]
            if strip_str(expected) in strip_str(col["text"]) or strip_str(col["text"]) in strip_str(expected):
                header_idx.append(idx)
                # remove expected_header[i]
                expected_header.pop(i)
                break

    if len(header_idx) < len(expected_header):
        return None

    new_table = []
    for row in table:
        new_row = []
        for idx in header_idx:
            new_row.append(row[idx])
        new_table.append(new_row)
    return new_table


def _extract_table(cells, expected_header, expected_row):
    table = extract_simple(cells)

    if len(expected_header) == 0:
        return table

    # 1. check if expected_header length is same with table[0]
    if len(expected_header) == len(table[0]):
        return table
    
    # check if actual table headers are too short
    if len(expected_header) != 0 and len(table[0]) / len(expected_header) <= 0.5:
        return None
    
    # check if expected headers are too short
    if len(table[0]) != 0 and len(expected_header) / len(table[0]) <= 0.5:
        return None

    table_without_empty_header = extract_simple_ignoring_empty_header(cells)

    # 2. check if expected_header legnth is same with table_without_empty
    if len(expected_header) == len(table_without_empty_header[0]):
        return table_without_empty_header

    # 3. match on header
    if len(table[0]) > len(expected_header):
        # try to match expected_header with table[0]
        ret = extract_table_from_table_by_matching_header(
            table, expected_header)
        if ret != None:
            return ret
        # try to match expected_header with table[0] (contains)
        ret = extract_table_from_table_by_matching_header_contains(
            table, expected_header)
        if ret != None:
            return ret
    
    return table


def fill_columns_for_each_row_with_max_column_count(table):
    max_column_count = 0
    for row in table:
        if len(row) > max_column_count:
            max_column_count = len(row)
    for row in table:
        while len(row) < max_column_count:
            row.append({"text": "", "cell": None})
    return table


def extract_table(cells, expected_header, expected_row):
    table = _extract_table(cells, expected_header, expected_row)
    if table == None:
        return None
    else:
        # use expected header instead of table[0]
        if len(expected_header) != 0:
            table.pop(0)
            expected_header_as_row = []
            for col in expected_header:
                expected_header_as_row.append({"text": col, "cell": None})
            table.insert(0, expected_header_as_row)
        fill_columns_for_each_row_with_max_column_count(table)
        return table


def put_extracted_table_to_dict(table, convertedWidth, convertedHeight, table_idx, mapper, read_id, export_dict, var_to_rect_fn):
    if table == None:
        return

    # remove header
    table = table[1:]

    # put
    for i in range(len(mapper)):
        for row_idx in range(len(table)):
            key = read_id + "." + "table_" + \
                str(table_idx) + "." + mapper[i] + "_" + str(row_idx)
            export_dict[key] = table[row_idx][i]["text"]
            if "cell" in table[row_idx][i] and table[row_idx][i]["cell"] != None:
                var_to_rect_fn(key, convert_boundingPoly_to_ratio(
                    table[row_idx][i]["cell"]["boundingPoly"], convertedWidth, convertedHeight))

    return
