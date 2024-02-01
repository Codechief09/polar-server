def min_max_for_boundingPoly(boundingPoly):
    vertices = boundingPoly["vertices"]
    # min x for boundingPoly
    min_x = 99999999
    # max x for boundingPoly
    max_x = -99999999
    # min y for boundingPoly
    min_y = 99999999
    # max y for boundingPoly
    max_y = -99999999
    for vertex in vertices:
        if vertex["x"] < min_x:
            min_x = vertex["x"]
        if vertex["x"] > max_x:
            max_x = vertex["x"]
        if vertex["y"] < min_y:
            min_y = vertex["y"]
        if vertex["y"] > max_y:
            max_y = vertex["y"]
    return min_x, min_y, max_x, max_y


def get_width_height(boundingPoly):
    min_x, min_y, max_x, max_y = min_max_for_boundingPoly(boundingPoly)
    return max_x - min_x, max_y - min_y


def get_center_of_bounding_poly(boundingPoly):
    min_x, min_y, max_x, max_y = min_max_for_boundingPoly(boundingPoly)
    return min_x + (max_x - min_x) / 2, min_y + (max_y - min_y) / 2


def is_inside(boundingPoly, boundingPoly2):
    fieldBdx = min_max_for_boundingPoly(boundingPoly)
    field_center_x = fieldBdx[0] + (fieldBdx[2] - fieldBdx[0]) / 2
    field_center_y = fieldBdx[1] + (fieldBdx[3] - fieldBdx[1]) / 2
    tableBdx = min_max_for_boundingPoly(boundingPoly2)
    if field_center_x > tableBdx[0] and field_center_x < tableBdx[2] and field_center_y > tableBdx[1] and field_center_y < tableBdx[3]:
        return True
    return False


def is_overlap(boundingPoly, boundingPoly2):
    fieldBdx = min_max_for_boundingPoly(boundingPoly)
    tableBdx = min_max_for_boundingPoly(boundingPoly2)
    if fieldBdx[0] > tableBdx[2] or fieldBdx[2] < tableBdx[0] or fieldBdx[1] > tableBdx[3] or fieldBdx[3] < tableBdx[1]:
        return False
    return True


def overlap_percentage(boundingPoly, boundingPoly2):
    fieldBdx = min_max_for_boundingPoly(boundingPoly)
    tableBdx = min_max_for_boundingPoly(boundingPoly2)
    if fieldBdx[0] > tableBdx[2] or fieldBdx[2] < tableBdx[0] or fieldBdx[1] > tableBdx[3] or fieldBdx[3] < tableBdx[1]:
        return 0
    overlap_area = (min(fieldBdx[2], tableBdx[2]) - max(fieldBdx[0], tableBdx[0])) * (
        min(fieldBdx[3], tableBdx[3]) - max(fieldBdx[1], tableBdx[1]))
    field_area = (fieldBdx[2] - fieldBdx[0]) * (fieldBdx[3] - fieldBdx[1])
    return overlap_area / field_area


def get_table_rect(table):
    min_x = 99999999
    min_y = 99999999
    max_x = -99999999
    max_y = -99999999
    for cell in table["cells"]:
        cellBdx = min_max_for_boundingPoly(cell["boundingPoly"])
        if cellBdx[0] < min_x:
            min_x = cellBdx[0]
        if cellBdx[1] < min_y:
            min_y = cellBdx[1]
        if cellBdx[2] > max_x:
            max_x = cellBdx[2]
        if cellBdx[3] > max_y:
            max_y = cellBdx[3]
    return min_x, min_y, max_x, max_y


def get_table_rect_as_boundingPoly(table, offset=5):
    min_x, min_y, max_x, max_y = get_table_rect(table)
    min_x += offset
    min_y += offset
    max_x -= offset
    max_y -= offset
    return {
        "vertices": [
            {"x": min_x, "y": min_y},
            {"x": max_x, "y": min_y},
            {"x": max_x, "y": max_y},
            {"x": min_x, "y": max_y}
        ]
    }


def parse_general_data_into_text_by_line(response_json, avoidTables=False):
    avoidBoundings = []
    # get boundingPolys from tables
    if avoidTables:
        if "tables" in response_json['images'][0]:
            tables = response_json["images"][0]["tables"]
            for table_ref in tables:
                # table's boundingPoly is not accurate, so we use cells' boundingPolys
                avoidBoundings.append(
                    get_table_rect_as_boundingPoly(table_ref))
    text = ''
    for field in response_json['images'][0]['fields']:
        # ignore field if it is in a avoidBoundings
        if avoidTables:
            ignore = False
            for avoidBounding in avoidBoundings:
                if is_inside(field['boundingPoly'], avoidBounding):
                    ignore = True
            if ignore:
                continue
        if text != "" and text[-1] != '\n':
            text += " "
        text += field['inferText']
        if field["lineBreak"]:
            text += '\n'
    return text


def find_overlap_fields(response_json, boundingPoly):
    target_width, target_height = get_width_height(boundingPoly)
    fields = []
    for field in response_json['images'][0]['fields']:
        if is_overlap(field['boundingPoly'], boundingPoly):
            width, height = get_width_height(field['boundingPoly'])
            fields.append({
                "field": field,
                "percentage": overlap_percentage(field['boundingPoly'], boundingPoly),
                "width_similarity": width / target_width,
                "height_similarity": height / target_height,
            })
    return fields


def parse_general_data_into_text_by_line_but_export_table_data_if_text_is_in_table(response_json):
    avoidBoundings = []
    # get boundingPolys from tables
    if "tables" in response_json['images'][0]:
        tables = response_json["images"][0]["tables"]
        parsed_tables = parse_general_tables_into_arrays(response_json)
        for table_ref in tables:
            # table's boundingPoly is not accurate, so we use cells' boundingPolys
            avoidBoundings.append(get_table_rect_as_boundingPoly(table_ref))
    text = ''
    tableAlreadyOutput = []
    for field in response_json['images'][0]['fields']:
        # ignore field if it is in a avoidBoundings
        ignore = False
        tableIdx = -1
        for i, avoidBounding in enumerate(avoidBoundings):
            if is_inside(field['boundingPoly'], avoidBounding):
                ignore = True
                tableIdx = i
        if ignore:
            # output table
            if tableIdx not in tableAlreadyOutput:
                table = parsed_tables[tableIdx]
                table_text = table_to_csv_text(table)
                text += "\n[table]\n"
                text += table_text
                text += "\n"
                tableAlreadyOutput.append(tableIdx)
            continue
        if text != "" and text[-1] != '\n':
            text += " "
        text += field['inferText']
        if field["lineBreak"]:
            text += '\n'
    return text


def parse_general_data_get_table_befores(response_json):
    avoidBoundings = []
    # get boundingPolys from tables
    if "tables" in response_json['images'][0]:
        tables = response_json["images"][0]["tables"]
        parsed_tables = parse_general_tables_into_arrays(response_json)
        for table_ref in tables:
            # table's boundingPoly is not accurate, so we use cells' boundingPolys
            avoidBoundings.append(get_table_rect_as_boundingPoly(table_ref))
    else:
        return []
    text = ''
    tableAlreadyOutput = []
    datas = []
    for field in response_json['images'][0]['fields']:
        # ignore field if it is in a avoidBoundings
        ignore = False
        tableIdx = -1
        for i, avoidBounding in enumerate(avoidBoundings):
            if is_inside(field['boundingPoly'], avoidBounding):
                ignore = True
                tableIdx = i
        if ignore:
            # output table
            if tableIdx not in tableAlreadyOutput:
                tableAlreadyOutput.append(tableIdx)
                datas.append(text)
                text = ""
            continue
        if text != "" and text[-1] != '\n':
            text += " "
        text += field['inferText']
        if field["lineBreak"]:
            text += '\n'
    if text != "":
        datas.append(text)
    return datas


def parse_general_tables_into_arrays(response_json):
    if "tables" not in response_json['images'][0]:
        return []
    tables = response_json["images"][0]["tables"]
    arrs = []
    for table_ref in tables:
        # get table
        cells = table_ref["cells"]
        # get number of rows and columns
        rows = 0
        columns = 0
        for cell in cells:
            rowSpan = cell["rowSpan"]
            rowIndex = cell["rowIndex"]
            columnSpan = cell["columnSpan"]
            columnIndex = cell["columnIndex"]
            # check if rows and columns are enough
            if rows < rowIndex + rowSpan:
                rows = rowIndex + rowSpan
            if columns < columnIndex + columnSpan:
                columns = columnIndex + columnSpan
        # create table
        table = []
        for i in range(rows):
            table.append([])
            for j in range(columns):
                table[i].append("")
        # fill table
        for cell in cells:
            rowSpan = cell["rowSpan"]
            rowIndex = cell["rowIndex"]
            columnSpan = cell["columnSpan"]
            columnIndex = cell["columnIndex"]
            text = ""
            for line in cell["cellTextLines"]:
                if text != "":
                    text += "\n"
                current_line = ""
                for word in line["cellWords"]:
                    if current_line != "":
                        current_line += " "
                    current_line += word["inferText"]
                text += current_line
            for i in range(rowIndex, rowIndex + rowSpan):
                for j in range(columnIndex, columnIndex + columnSpan):
                    table[i][j] = text
        # add table to array
        arrs.append(table)
    return arrs


def convert_boundingPoly_to_ratio(boundingPoly, width, height):
    # boundingPoly is {'vertices': [{'x': 97.0, 'y': 256.0}, {'x': 206.0, 'y': 256.0}, {'x': 206.0, 'y': 275.0}, {'x': 97.0, 'y': 275.0}]}
    # convert to ratio
    return {
        "vertices": [
            {"x": boundingPoly["vertices"][0]["x"] / width,
                "y": boundingPoly["vertices"][0]["y"] / height},
            {"x": boundingPoly["vertices"][1]["x"] / width,
                "y": boundingPoly["vertices"][1]["y"] / height},
            {"x": boundingPoly["vertices"][2]["x"] / width,
                "y": boundingPoly["vertices"][2]["y"] / height},
            {"x": boundingPoly["vertices"][3]["x"] / width,
                "y": boundingPoly["vertices"][3]["y"] / height},
        ]
    }


def parse_general_tables_into_arrays_for_rect(response_json):
    if "tables" not in response_json['images'][0]:
        return []
    tables = response_json["images"][0]["tables"]
    arrs = []
    convertedWidth = response_json["images"][0]["convertedImageInfo"]["width"]
    convertedHeight = response_json["images"][0]["convertedImageInfo"]["height"]
    for table_ref in tables:
        # get table
        cells = table_ref["cells"]
        # get number of rows and columns
        rows = 0
        columns = 0
        for cell in cells:
            rowSpan = cell["rowSpan"]
            rowIndex = cell["rowIndex"]
            columnSpan = cell["columnSpan"]
            columnIndex = cell["columnIndex"]
            # check if rows and columns are enough
            if rows < rowIndex + rowSpan:
                rows = rowIndex + rowSpan
            if columns < columnIndex + columnSpan:
                columns = columnIndex + columnSpan
        # create table
        table = []
        for i in range(rows):
            table.append([])
            for j in range(columns):
                table[i].append(None)
        # fill table
        for cell in cells:
            rowSpan = cell["rowSpan"]
            rowIndex = cell["rowIndex"]
            columnSpan = cell["columnSpan"]
            columnIndex = cell["columnIndex"]
            for i in range(rowIndex, rowIndex + rowSpan):
                for j in range(columnIndex, columnIndex + columnSpan):
                    table[i][j] = convert_boundingPoly_to_ratio(
                        cell["boundingPoly"], convertedWidth, convertedHeight)
        # add table to array
        arrs.append(table)
    return arrs


def tables_to_csv_text(tables):
    text = ""
    for table in tables:
        text += table_to_csv_text(table)
        text += "\n"
    return text


def table_to_csv_text(table):
    text = ""
    for row in table:
        line = ""
        cellBuilt = False
        for cell in row:
            cell = cell.strip()
            if cellBuilt:
                line += ","
            cellBuilt = True
            if "\"" in cell:
                cell = cell.replace("\"", "\"\"")
            if "," in cell or "\n" in cell or "\"" in cell:
                line += "\"" + cell + "\""
            else:
                line += cell
        text += line + "\n"
    return text


def getTextFromCell(cell):
    cellTextLines = cell["cellTextLines"]
    # get text
    text = ""
    for cellTextLine in cellTextLines:
        cellWords = cellTextLine["cellWords"]
        word = ""
        for cellWord in cellWords:
            if "inferText" in cellWord:
                if word != "" and cellWord["inferText"] != "":
                    word += " "
                word += cellWord["inferText"]
        if word != "" and text != "":
            text += "\n"
        text += word
    return text


def extract_table_from_table_by_finding_column_name(clova_result, startRowFinderText, endRowFinderText):
    tables = []

    convertedWidth = clova_result["images"][0]["convertedImageInfo"]["width"]
    convertedHeight = clova_result["images"][0]["convertedImageInfo"]["height"]

    for table in clova_result["images"][0]["tables"]:
        cells = table["cells"]
        # find startRow
        startRow = -1
        # sort cell by rowIndex
        cells = sorted(cells, key=lambda x: x["rowIndex"])
        # find startRow
        for cell in cells:
            # get text
            text = getTextFromCell(cell)
            if startRowFinderText in text:
                startRow = cell["rowIndex"]
                break
        # check if startRow is found
        if startRow == -1:
            continue
        # find endRow
        endRow = -1
        if endRowFinderText != "":
            for cell in cells:
                # get text
                text = getTextFromCell(cell)
                if endRowFinderText in text:
                    endRow = cell["rowIndex"] - 1
                    break
        # check if endRow is found
        if endRow == -1:
            # find max row
            endRow = 0
            for cell in cells:
                if cell["rowIndex"] > endRow:
                    endRow = cell["rowIndex"]
        if endRow <= startRow:
            continue
        # create heder info
        headerInfo = {}
        for cell in cells:
            if cell["rowIndex"] == startRow:
                text = getTextFromCell(cell)
                for i in range(cell["columnIndex"], cell["columnIndex"] + cell["columnSpan"]):
                    headerInfo[i] = text
        # group cells by row
        rows = {}
        for cell in cells:
            if cell["rowIndex"] > startRow and cell["rowIndex"] <= endRow:
                if cell["rowIndex"] not in rows:
                    rows[cell["rowIndex"]] = []
                rows[cell["rowIndex"]].append(cell)
        # sort cells by column
        for row in rows:
            rows[row] = sorted(rows[row], key=lambda x: x["columnIndex"])
        # give header to cells
        for row in rows:
            usedHeaders = {}
            for cell in rows[row]:
                headerTitle = headerInfo[cell["columnIndex"]]
                if headerTitle not in usedHeaders:
                    cell["header"] = headerTitle
                    usedHeaders[headerTitle] = 0
                else:
                    cell["header"] = headerTitle + "_" + \
                        str(usedHeaders[headerTitle] + 1)
                    usedHeaders[headerTitle] += 1
        # get header list
        headerList = []
        for row in rows:
            for cell in rows[row]:
                if cell["header"] not in headerList:
                    headerList.append(cell["header"])
        datas = []
        datas.append(headerList)
        datas_rects = []
        datas_rects.append(headerList)
        for row in rows:
            data = []
            data_rect = []
            currentRow = rows[row]
            for header in headerList:
                found = False
                for cell in currentRow:
                    if cell["header"] == header:
                        data.append(getTextFromCell(cell))
                        data_rect.append(convert_boundingPoly_to_ratio(
                            cell["boundingPoly"], convertedWidth, convertedHeight))
                        found = True
                        break
                if not found:
                    data.append("")
                    data_rect.append(None)
            datas.append(data)
            datas_rects.append(data_rect)
        ignoredRowsBefore = {}
        ignoredRowsAfter = {}
        for cell in cells:
            if cell["rowIndex"] < startRow:
                if cell["rowIndex"] not in ignoredRowsBefore:
                    ignoredRowsBefore[cell["rowIndex"]] = []
                ignoredRowsBefore[cell["rowIndex"]].append(cell)
            if cell["rowIndex"] > endRow:
                if cell["rowIndex"] not in ignoredRowsAfter:
                    ignoredRowsAfter[cell["rowIndex"]] = []
                ignoredRowsAfter[cell["rowIndex"]].append(cell)
        # sort cells by column
        for row in ignoredRowsBefore:
            ignoredRowsBefore[row] = sorted(
                ignoredRowsBefore[row], key=lambda x: x["columnIndex"])
        for row in ignoredRowsAfter:
            ignoredRowsAfter[row] = sorted(
                ignoredRowsAfter[row], key=lambda x: x["columnIndex"])
        # construct text
        ignoredTextBefore = ""
        ignoredTextAfter = ""
        for row in ignoredRowsBefore:
            line = ""
            for cell in ignoredRowsBefore[row]:
                if line != "" and getTextFromCell(cell) != "":
                    line += " "
                line += getTextFromCell(cell)
            if ignoredTextBefore != "" and line != "":
                ignoredTextBefore += "\n"
            ignoredTextBefore += line
        for row in ignoredRowsAfter:
            line = ""
            for cell in ignoredRowsAfter[row]:
                if line != "" and getTextFromCell(cell) != "":
                    line += " "
                line += getTextFromCell(cell)
            if ignoredTextAfter != "" and line != "":
                ignoredTextAfter += "\n"
            ignoredTextAfter += line
        tables.append({
            "ignoredTextBefore": ignoredTextBefore,
            "ignoredTextAfter": ignoredTextAfter,
            "datas": datas,
            "datas_rects": datas_rects,
        })

    return tables
