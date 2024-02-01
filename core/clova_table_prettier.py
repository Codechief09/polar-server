from core.clova_table_utils import draw_boundingPoly, get_width_for_column, get_x_y_width_height, x_y_width_height_to_boundingPoly
from core.clova_ext import getTextFromCell


def get_converted_size(response_json):
    converted_width = response_json["images"][0]["convertedImageInfo"]["width"]
    converted_height = response_json["images"][0]["convertedImageInfo"]["height"]
    return converted_width, converted_height


def get_rows(cells):
    ret = dict()
    for cell in cells:
        row = cell["rowIndex"]
        if row not in ret:
            ret[row] = []
        ret[row].append(cell)
    # sort
    for row in ret:
        ret[row].sort(key=lambda x: x["columnIndex"])
    return ret


def get_most_common_columns_count(rows):
    return max(set([len(rows[row]) for row in rows]), key=list([len(rows[row]) for row in rows]).count)


def get_median_width_for_columns(rows, most_common_column_count):
    width_list_for_each_column = dict()
    for row in rows:
        if len(rows[row]) != most_common_column_count:
            continue
        for col in range(most_common_column_count):
            cell = rows[row][col]
            if col not in width_list_for_each_column:
                width_list_for_each_column[col] = []
            width_list_for_each_column[col].append(get_width_for_column(cell))
    return {col: sorted(width_list_for_each_column[col])[len(width_list_for_each_column[col]) // 2] for col in width_list_for_each_column}


def get_most_common_columnIndex_property_for_column(rows, most_common_column_count):
    columnIndex_property_for_column = dict()
    for row in rows:
        if len(rows[row]) != most_common_column_count:
            continue
        for col in range(most_common_column_count):
            cell = rows[row][col]
            if col not in columnIndex_property_for_column:
                columnIndex_property_for_column[col] = []
            columnIndex_property_for_column[col].append(cell["columnIndex"])
    return {col: max(set(columnIndex_property_for_column[col]), key=columnIndex_property_for_column[col].count) for col in columnIndex_property_for_column}


def pretty_cells(response_json, table_index, has_image, image, threshold=0.9, last_threshold=0.95):
    print("starting pretty cells...")
    # copy response_json just in case
    response_json = response_json.copy()
    # get clova info
    converted_width, converted_height = get_converted_size(response_json)
    # get cells
    cells = response_json["images"][0]["tables"][table_index]["cells"]

    # draw baseline for debugging purpose
    if has_image:
        draw_boundingPoly(image, cells, converted_width, converted_height)

    # get rows
    rows = get_rows(cells)

    # find most common column count
    most_common_column_count = get_most_common_columns_count(rows)

    # calc median
    median_width_list_for_each_column = get_median_width_for_columns(
        rows, most_common_column_count)

    # find most common columnIndex
    most_common_columnIndex_property_for_column = get_most_common_columnIndex_property_for_column(
        rows, most_common_column_count)

    # now, try to make it same width
    ret_cells = []
    for cells in rows.values():
        if len(cells) == most_common_column_count:
            # no need of changes
            ret_cells.append(cells)
            continue

        # get median width for target column
        def get_median_column_width(target_idx, if_not_exists=-1):
            if len(median_width_list_for_each_column) > target_idx:
                return median_width_list_for_each_column[target_idx]
            else:
                return if_not_exists

        # get current column width for target column
        def get_current_column_width(target_idx, if_not_exists=-1):
            if len(cells) > target_idx:
                return get_width_for_column(cells[target_idx])
            else:
                return if_not_exists

        # start processing
        try:
            new_cells = []
            reference_col_idx = 0
            current_col_idx = -1

            for cell in cells:
                # ptr
                current_col_idx += 1
                # check if current cell is already processed
                if "skip" in cell and cell["skip"]:
                    continue
                # update cell columnIndex
                if reference_col_idx not in most_common_columnIndex_property_for_column:
                    break
                cell["columnIndex"] = most_common_columnIndex_property_for_column[reference_col_idx]

                # Step 1.
                # check if current cell is same width as median
                # get current column width
                current_width = get_width_for_column(cell)
                # get median width
                median_width = median_width_list_for_each_column[reference_col_idx]
                if median_width == current_width:
                    new_cells.append(cell)
                    reference_col_idx += 1
                    continue

                # Step 2.
                # get next column median as a reference
                next_median_width = get_median_column_width(
                    reference_col_idx + 1, 0)
                # get next current column width
                current_next_width = get_current_column_width(
                    current_col_idx + 1, -1)

                next_x, next_y, next_width, next_height = get_x_y_width_height(
                    cell)

                # Step 3.
                # check if current cell is smaller than median
                if median_width > current_width:
                    # print("med > cur")
                    # if current cell is smaller than median, it needs to be merged
                    processed = False
                    # repeat until current cell is same width as median
                    # print("condition: " + str(median_width) + " >= " + str(current_width + current_next_width))
                    setCellTextLines = cell["cellTextLines"]
                    while True:
                        if median_width >= current_width + current_next_width and current_col_idx + 1 < len(cells):
                            # mark this as processed
                            processed = True
                            # find next cell and width to merge
                            if len(cells) < reference_col_idx + 1:
                                break
                            next_cell = cells[reference_col_idx + 1]
                            def getText(cell):
                                try:
                                    return getTextFromCell(cell)
                                except:
                                    return ""
                            # use next cell's text if current cell is empty
                            if getText(cell).strip() == "" and getText(next_cell).strip() != "":
                                setCellTextLines = next_cell["cellTextLines"]
                            next_cell_width = get_width_for_column(next_cell)
                            # mark next cell as skipping
                            next_cell["skip"] = True
                            # now its merging
                            current_width += next_cell_width
                            # seek next column for both
                            reference_col_idx += 1
                            current_col_idx += 1
                            # print("merge: " + str(reference_col_idx))
                            # print("remaining: " + str(current_width))
                            # print("median: " + str(median_width))
                            # get next column width or -1
                            current_next_width = get_current_column_width(
                                current_col_idx, -1)
                        elif median_width * last_threshold > current_width:
                            # print("still")
                            # still smmaler than median but no more column to merge
                            # so just making itself as median
                            # print("current: " + str(current_width) +
                            # " vs " + str(median_width))
                            current_width = median_width
                            # set next cell x as current x + current width
                            if len(cells) > reference_col_idx + 1:
                                next_cell_x = next_x + current_width
                                # print("next_cell_x: " + str(next_cell_x))
                                ncx, ncy, ncw, nch = get_x_y_width_height(
                                    cells[reference_col_idx + 1])
                                # print("current: " + str(ncx))
                                cells[reference_col_idx + 1]["boundingPoly"] = x_y_width_height_to_boundingPoly(
                                    next_cell_x, ncy, ncw - (next_cell_x - ncx), nch)
                            break
                        else:
                            break
                    # now its merged
                    # so just copy this cell as new cell
                    new_cell = cell.copy()
                    new_cell["boundingPoly"] = x_y_width_height_to_boundingPoly(
                        next_x, next_y, current_width, next_height)
                    if setCellTextLines != None:
                        new_cell["cellTextLines"] = setCellTextLines
                    new_cells.append(new_cell)
                    # just move to next column if not processed
                    if not processed:
                        reference_col_idx += 1
                # Step 4.
                # check if current cell is wider than median
                elif median_width + next_median_width * threshold <= current_width:
                    # print("cur > med")
                    # if current cell is wider than median, it needs to be splitted
                    next_predicate_width = median_width
                    first = True
                    while next_predicate_width <= current_width:
                        # split cell
                        new_cell = cell.copy()
                        new_cell["columnIndex"] = most_common_columnIndex_property_for_column[reference_col_idx]
                        new_cell["boundingPoly"] = x_y_width_height_to_boundingPoly(
                            next_x, next_y, median_width, next_height)
                        if first:
                            first = False
                        else:
                            new_cell["cellTextLines"] = []
                        new_cells.append(new_cell)
                        # update for the next
                        next_x += median_width
                        # update current_width
                        current_width -= median_width
                        # update reference_col_idx
                        reference_col_idx += 1
                        # check if there is next column
                        if len(median_width_list_for_each_column) > reference_col_idx:
                            # this width would be applied next
                            median_width = median_width_list_for_each_column[reference_col_idx]
                            next_predicate_width = median_width * last_threshold
                            if len(median_width_list_for_each_column) - 1 == reference_col_idx:
                                # last one should be multiplied by last_threshold
                                # to make it flexible
                                next_predicate_width *= last_threshold
                        else:
                            # no more column
                            break
                        # print("splitting: " + str(reference_col_idx))
                        # print("remaining: " + str(current_width))
                        # print("median: " + str(median_width))
                # Step 5.
                # nothing to do. just append it
                else:
                    # same
                    # print("same")
                    new_cells.append(cell)
                    reference_col_idx += 1
            if has_image:
                draw_boundingPoly(image, new_cells, converted_width,
                                  converted_height, (255, 0, 0), 6, 6, 2, "a")
            ret_cells.append(new_cells)
        except:
            # we ignores any errors here since it might be caused by
            # unexpected cell structure
            # but we may need traceback to resolve unexpected issue
            # so we print it here
            print("failed to process cells")
            import traceback
            traceback.print_exc()

    return ret_cells, image
