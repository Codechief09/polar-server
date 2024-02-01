import time
import math
import itertools
from core.clova_ext import get_center_of_bounding_poly


def calc_levenshtein(text1, text2):
    if len(text1) < len(text2):
        return calc_levenshtein(text2, text1)

    # len(text1) >= len(text2)
    if len(text2) == 0:
        return len(text1)

    previous_row = range(len(text2) + 1)
    for i, c1 in enumerate(text1):
        current_row = [i + 1]
        for j, c2 in enumerate(text2):
            # j+1 instead of j since previous_row and current_row are one character longer
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1       # than text2
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def find_lowest_levenshtein(text, fields):
    lowest = 999999999
    lowest_field = None
    for field in fields:
        result = calc_levenshtein(text, field["inferText"])
        if result < lowest:
            lowest = result
            lowest_field = field
    if lowest < 5:
        return lowest_field
    else:
        return None


def find_low_levenshteins(text, fields):
    ret_fields = []
    for field in fields:
        result = calc_levenshtein(text, field["inferText"])
        if result < 5:
            ret_fields.append({
                "distance": result,
                "field": field,
            })
    # sort by distance and field.y
    ret_fields = sorted(ret_fields, key=lambda x: (
        x["distance"], x["field"]["boundingPoly"]["vertices"][0]["y"]))

    if len(ret_fields) > 10:
        ret_fields = ret_fields[:10]
    else:
        return ret_fields


def find_fields_by_text(target, text, methods=["exact"], maxFields=50):
    # find fields from target by inferText
    fields = []
    if "exact" in methods:
        for i in range(len(target)):
            if target[i]["inferText"] == text and target[i] not in fields and len(fields) < maxFields:
                fields.append(target[i])
    if "leven" in methods:
        leven = find_lowest_levenshtein(text, target)
        if leven != None and leven not in fields and len(fields) < maxFields:
            fields.append(leven)
    if "startswith" in methods:
        for i in range(len(target)):
            if target[i]["inferText"].startswith(text):
                if len(fields) < maxFields and target[i] not in fields:
                    fields.append(target[i])
    if "startswith-target" in methods:
        for i in range(len(target)):
            if text.startswith(target[i]["inferText"]):
                if len(fields) < maxFields and target[i] not in fields:
                    fields.append(target[i])
    if "endswith" in methods:
        for i in range(len(target)):
            if target[i]["inferText"].endswith(text):
                if len(fields) < maxFields and target[i] not in fields:
                    fields.append(target[i])
    if "endswith-target" in methods:
        for i in range(len(target)):
            if text.endswith(target[i]["inferText"]):
                if len(fields) < maxFields and target[i] not in fields:
                    fields.append(target[i])
    if "contains" in methods:
        for i in range(len(target)):
            if text in target[i]["inferText"]:
                if len(fields) < maxFields and target[i] not in fields:
                    fields.append(target[i])
    if "contains-target" in methods:
        for i in range(len(target)):
            if target[i]["inferText"] in text:
                if len(fields) < maxFields and target[i] not in fields:
                    fields.append(target[i])
    # NOT RECOMMENDED
    if "leven-multi" in methods:
        levens = find_low_levenshteins(text, target)
        for leven in levens:
            if len(fields) < maxFields and leven["field"] not in fields:
                fields.append(leven["field"])
    return fields

# get distance between two boundingPoly


def get_distance(boundingPoly1, boundingPoly2):
    # get center of boundingPoly1
    center1 = get_center_of_bounding_poly(boundingPoly1)
    # get center of boundingPoly2
    center2 = get_center_of_bounding_poly(boundingPoly2)
    # get distance between center1 and center2
    distance = math.sqrt((center1[0] - center2[0])
                         ** 2 + (center1[1] - center2[1]) ** 2)
    return distance


def check_document_similarity(sampled_fields, target_fields):
    # print("checking document similarity...")
    origin = get_center_of_bounding_poly(sampled_fields[0]["boundingPoly"])
    origin_distance = get_distance(
        sampled_fields[0]["boundingPoly"], sampled_fields[-1]["boundingPoly"])

    distances = []
    for field in sampled_fields[1:]:
        field_center = get_center_of_bounding_poly(field["boundingPoly"])
        x_distance = origin[0] - field_center[0]
        y_distance = origin[1] - field_center[1]
        x_distance /= origin_distance
        y_distance /= origin_distance
        distances.append([x_distance, y_distance])

    start_time = time.time()
    fields_possibilities = []
    for field in sampled_fields:
        maxFields = 50
        methods = ["exact", "leven", "startswith", "startswith-target",
                   "contains", "contains-target", "endswith", "endswith-target"]
        if len(sampled_fields) > 5:
            methods = ["exact", "leven", "startswith",
                       "startswith-target", "endswith", "endswith-target"]
        if len(sampled_fields) > 10:
            methods = ["exact", "leven", "startswith", "startswith-target"]
            maxFields = 30
        if len(sampled_fields) > 15:
            methods = ["exact", "leven"]
            maxFields = 10
        fields_possibilities.append(find_fields_by_text(
            target_fields, field["inferText"], methods))
    # print inferText from fields_possibilities

    fields_combination = list(itertools.product(*fields_possibilities))

    end_time = time.time()
    print("time: ", end_time - start_time)
    print("combinations: " + str(len(fields_combination)))

    best_similarity = 0
    best_combination = None

    if len(fields_combination) > 1000000:
        print("too many combinations. sampling...")
        fields_combination = fields_combination[:1000000]

    for combination in fields_combination:
        origin = get_center_of_bounding_poly(combination[0]["boundingPoly"])
        origin_distance = get_distance(
            combination[0]["boundingPoly"], combination[-1]["boundingPoly"])
        if origin_distance == 0:
            continue
        target_distances = []

        for i in range(1, len(combination)):
            field_center = get_center_of_bounding_poly(
                combination[i]["boundingPoly"])
            x_distance = origin[0] - field_center[0]
            y_distance = origin[1] - field_center[1]
            x_distance /= origin_distance
            y_distance /= origin_distance
            target_distances.append([x_distance, y_distance])

        # get similarity between distances and target_distances
        similarity = 0
        for i in range(len(distances)):
            similarity += math.sqrt((distances[i][0] - target_distances[i][0]) ** 2 + (
                distances[i][1] - target_distances[i][1]) ** 2)
        similarity /= len(distances)
        similarity = 1 - similarity

        if best_similarity < similarity:
            best_similarity = similarity
            best_combination = combination

    end_time = time.time()
    print("comparison time: ", end_time - start_time)
    # print("done checking document similarity")
    return best_similarity, best_combination
