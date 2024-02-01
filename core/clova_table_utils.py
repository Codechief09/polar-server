import cv2


def img_add_msg(img, message, x, y, color):
    cv2.putText(img, message, (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, 2, color, 4)
    return img


def draw_boundingPoly(image, cells, converted_width, converted_height, color=(0, 0, 255), offset_x=0, offset_y=0, scale=2, text=""):
    for cell in cells:
        boundingPoly = cell["boundingPoly"]
        x0 = int(boundingPoly["vertices"][0]["x"] /
                 converted_width * image.shape[1])
        y0 = int(boundingPoly["vertices"][0]["y"] /
                 converted_height * image.shape[0])
        x1 = int(boundingPoly["vertices"][1]["x"] /
                 converted_width * image.shape[1])
        y1 = int(boundingPoly["vertices"][1]["y"] /
                 converted_height * image.shape[0])
        x2 = int(boundingPoly["vertices"][2]["x"] /
                 converted_width * image.shape[1])
        y2 = int(boundingPoly["vertices"][2]["y"] /
                 converted_height * image.shape[0])
        x3 = int(boundingPoly["vertices"][3]["x"] /
                 converted_width * image.shape[1])
        y3 = int(boundingPoly["vertices"][3]["y"] /
                 converted_height * image.shape[0])
        cv2.line(image, (x0 + offset_x, y0 + offset_y),
                 (x1 + offset_x, y1 + offset_y), color, scale)
        cv2.line(image, (x1 + offset_x, y1 + offset_y),
                 (x2 + offset_x, y2 + offset_y), color, scale)
        cv2.line(image, (x2 + offset_x, y2 + offset_y),
                 (x3 + offset_x, y3 + offset_y), color, scale)
        cv2.line(image, (x3 + offset_x, y3 + offset_y),
                 (x0 + offset_x, y0 + offset_y), color, scale)
        # put text to x0, y0
        image = img_add_msg(image, str(
            cell["columnIndex"]), x0 + 10, y0 + 10, color)


def get_width_for_column(cell):
    boundingPoly = cell["boundingPoly"]
    x0 = boundingPoly["vertices"][0]["x"]
    x1 = boundingPoly["vertices"][1]["x"]
    x2 = boundingPoly["vertices"][2]["x"]
    x3 = boundingPoly["vertices"][3]["x"]
    max_x = max(x0, x1, x2, x3)
    min_x = min(x0, x1, x2, x3)
    return max_x - min_x


def get_x_y_width_height(cell):
    boundingPoly = cell["boundingPoly"]
    x0 = boundingPoly["vertices"][0]["x"]
    y0 = boundingPoly["vertices"][0]["y"]
    x1 = boundingPoly["vertices"][1]["x"]
    y1 = boundingPoly["vertices"][1]["y"]
    x2 = boundingPoly["vertices"][2]["x"]
    y2 = boundingPoly["vertices"][2]["y"]
    x3 = boundingPoly["vertices"][3]["x"]
    y3 = boundingPoly["vertices"][3]["y"]
    max_x = max(x0, x1, x2, x3)
    min_x = min(x0, x1, x2, x3)
    max_y = max(y0, y1, y2, y3)
    min_y = min(y0, y1, y2, y3)
    return min_x, min_y, max_x - min_x, max_y - min_y


def x_y_width_height_to_boundingPoly(x, y, width, height):
    boundingPoly = dict()
    boundingPoly["vertices"] = []
    boundingPoly["vertices"].append(dict())
    boundingPoly["vertices"].append(dict())
    boundingPoly["vertices"].append(dict())
    boundingPoly["vertices"].append(dict())
    boundingPoly["vertices"][0]["x"] = x
    boundingPoly["vertices"][0]["y"] = y
    boundingPoly["vertices"][1]["x"] = x + width
    boundingPoly["vertices"][1]["y"] = y
    boundingPoly["vertices"][2]["x"] = x + width
    boundingPoly["vertices"][2]["y"] = y + height
    boundingPoly["vertices"][3]["x"] = x
    boundingPoly["vertices"][3]["y"] = y + height
    return boundingPoly
