
from core.clova import general, infer
from core.clova_ext import parse_general_data_into_text_by_line, parse_general_tables_into_arrays, table_to_csv_text, parse_general_data_into_text_by_line_but_export_table_data_if_text_is_in_table, parse_general_data_get_table_befores, parse_general_tables_into_arrays_for_rect, convert_boundingPoly_to_ratio
from core.clova_ext import find_overlap_fields
from core.gpt import completion
from core.default_prompts import default_prompt
from core.clova_ext import extract_table_from_table_by_finding_column_name
from core.gpt_ext import embed, cosine_similarity
from core.workflow_read_provider.table_extraction import table_extract_strategy_pretty
import js2py
import csv
import re
import unicodedata
from core.js_runner import run_js
import hashlib
from core.ocr_api import predicts
from core.openai_client import get_openai_client

# TODO: split files by provider
def workflow_read(json, image, export_dict, on_memory_dict, tmp_dict, costs_dict=dict(), user_id=""):
    # json example
    """
    {
        "id": "general",
        "provider": "clova-general"
    }
    """
    read_id = json['id']

    def set_cost(key, val):
        if key not in costs_dict:
            costs_dict[key] = val
        else:
            costs_dict[key] += val

    def var_to_rect(var_key, rect):
        if "var_to_rect" not in on_memory_dict:
            on_memory_dict["var_to_rect"] = dict()
        on_memory_dict["var_to_rect"][var_key] = rect

    def get_var_to_rect(var_key):
        try:
            if "var_to_rect" not in on_memory_dict:
                return None
            if var_key not in on_memory_dict["var_to_rect"]:
                return None
            if on_memory_dict["var_to_rect"][var_key] == None:
                return None
            if "vertices" not in on_memory_dict["var_to_rect"][var_key]:
                return None
            return on_memory_dict["var_to_rect"][var_key]["vertices"]
        except:
            return None

    def header_duplication_fixer(header):
        new_header = []
        col_counter = dict()
        for col in header:
            if col not in col_counter:
                col_counter[col] = -1
            col_counter[col] += 1
            if col_counter[col] == 0:
                new_header.append(col)
            else:
                while col + "_" + str(col_counter[col]) in new_header:
                    col_counter[col] += 1
                new_header.append(col + "_" + str(col_counter[col]))
        return new_header

    # prepare
    # get input_text for any input
    input_text = ""
    if "input" in json:
        input_key = json["input"].replace("{", "").replace("}", "")
        # check if input_key is contained
        if input_key in export_dict:
            # get variable from dict
            input_text = export_dict[input_key]

    # now operate
    if json["provider"] == "clova-general":
        # =====================
        # Clova general
        # =====================
        # print("generaling...")
        set_cost("general-table-calls", 1)
        # table detection should be always true
        if "clova_general" not in tmp_dict:
            shrinkThreshold = -1
            if "version" in json and json["version"] != "" and json["version"] != None and int(json["version"]) > 1:
                if "shrinkThreshold" in json:
                    shrinkThreshold = json["shrinkThreshold"]
                else:
                    shrinkThreshold = 1700
            clova_result = general(image, True, shrinkThreshold)
            tmp_dict["clova_general"] = clova_result
        else:
            clova_result = tmp_dict["clova_general"]
        # print("done")
        text = parse_general_data_into_text_by_line(clova_result)
        # export to dict
        export_dict[read_id + "." + "text"] = text
        # export table to dict
        tables = parse_general_tables_into_arrays(clova_result)
        tables_rects = parse_general_tables_into_arrays_for_rect(clova_result)
        for i in range(len(tables)):
            table = tables[i]
            table_rects = tables_rects[i]
            export_dict[read_id + "." + "table_" +
                        str(i) + ".csv"] = table_to_csv_text(table)
            # export to dict
            if "version" in json and json["version"] != "" and json["version"] != None and int(json["version"]) > 2:
                # version > 2
                # export to dict using normal reader to keep same column name
                raw_reader = csv.reader(table_to_csv_text(table).splitlines())
                header = []
                j = -1
                for row in raw_reader:
                    j += 1
                    if j == 0:
                        header = header_duplication_fixer(row)
                        continue
                    col_id = -1
                    for col in row:
                        col_id += 1
                        if col == None:
                            col = ""
                        export_dict[read_id + "." + "table_" +
                                    str(i) + "." + header[col_id] + "_" + str(j)] = col
                        export_dict[read_id + "." + "table_" +
                                    str(i) + ".col_" + str(col_id) + "_" + str(j)] = col
                        try:
                            var_to_rect(read_id + "." + "table_" +
                                        str(i) + "." + header[col_id] + "_" + str(j), table_rects[j][col_id])
                            var_to_rect(read_id + "." + "table_" +
                                        str(i) + ".col_" + str(col_id) + "_" + str(j), table_rects[j][col_id])
                        except:
                            print("err while var_to_rect")
                            import traceback
                            traceback.print_exc()
                            pass
                        set_cost("items", 1)
                        set_cost("items-general-table", 1)
            else:
                # version < 3
                # export to dict for each
                csv_reader = csv.DictReader(
                    table_to_csv_text(table).splitlines())
                j = -1
                for row in csv_reader:
                    j += 1
                    col_id = -1
                    for key, value in row.items():
                        col_id += 1
                        if key == None:
                            key = ""
                        if value == None:
                            value = [""]
                        export_dict[read_id + "." + "table_" +
                                    str(i) + "." + key + "_" + str(j)] = "".join(value)
                        export_dict[read_id + "." + "table_" +
                                    str(i) + ".col_" + str(col_id) + "_" + str(j)] = "".join(value)
                        if "".join(value) != "":
                            set_cost("items", 1)
                            set_cost("items-general-table", 1)
        # export table avoided text to dict
        text = parse_general_data_into_text_by_line(clova_result, True)
        export_dict[read_id + "." + "text_without_table"] = text
        # export table avoided text to dict but concatenate table csv
        text = parse_general_data_into_text_by_line_but_export_table_data_if_text_is_in_table(
            clova_result)
        export_dict[read_id + "." + "text_with_csv"] = text
        befores = parse_general_data_get_table_befores(clova_result)
        for i in range(len(befores)):
            if i < len(tables):
                export_dict[read_id + "." + "table_" +
                            str(i) + ".before"] = befores[i]
            else:
                export_dict[read_id + "." + "footer"] = befores[i]
    elif json["provider"] == "table-extraction":
        startRowFinderText = json["startRowFinderText"]
        endRowFinderText = json["endRowFinderText"]
        clova_result = None
        if "clova_general" in tmp_dict:
            clova_result = tmp_dict["clova_general"]
        else:
            clova_result = general(image, True)
            set_cost("general-table-calls", 1)
            tmp_dict["clova_general"] = clova_result
        # strategies
        table_strategy = "extract"
        if "strategy" in json and json["strategy"] != "" and json["strategy"] != None:
            table_strategy = json["strategy"]

        if table_strategy == "extract":
            tables = extract_table_from_table_by_finding_column_name(
                clova_result, startRowFinderText, endRowFinderText)
            for i in range(len(tables)):
                export_dict[read_id + "." + "table_" +
                            str(i) + ".csv"] = table_to_csv_text(tables[i]["datas"])
                export_dict[read_id + "." + "table_" +
                            str(i) + ".before"] = tables[i]["ignoredTextBefore"]
                export_dict[read_id + "." + "table_" +
                            str(i) + ".after"] = tables[i]["ignoredTextAfter"]
                # export to dict for each
                csv_reader = csv.DictReader(
                    table_to_csv_text(tables[i]["datas"]).splitlines())
                table_rects = tables[i]["datas_rects"]
                j = -1
                for row in csv_reader:
                    j += 1
                    col_id = -1
                    for key, value in row.items():
                        col_id += 1
                        if key == None:
                            key = ""
                        if value == None:
                            value = [""]
                        export_dict[read_id + "." + "table_" +
                                    str(i) + "." + key + "_" + str(j)] = "".join(value)
                        export_dict[read_id + "." + "table_" +
                                    str(i) + ".col_" + str(col_id) + "_" + str(j)] = "".join(value)
                        try:
                            var_to_rect(read_id + "." + "table_" +
                                        str(i) + "." + key + "_" + str(j), table_rects[j + 1][col_id])
                            var_to_rect(read_id + "." + "table_" +
                                        str(i) + ".col_" + str(col_id) + "_" + str(j), table_rects[j + 1][col_id])
                        except:
                            print("err while var_to_rect")
                            import traceback
                            traceback.print_exc()
                            pass
                        if "".join(value) != "":
                            set_cost("items", 1)
                            set_cost("items-table-extraction", 1)
        elif table_strategy == "pretty":
            table_extract_strategy_pretty(
                read_id, tmp_dict, json, export_dict, var_to_rect)
    elif json["provider"] == "clova-rect":
        # =====================
        # Clova bondingBox
        # =====================
        set_cost("clova-rect-calls", 1)
        if "clova_infer" in tmp_dict:
            clova_result = tmp_dict["clova_infer"]
        else:
            clova_result = infer(
                image, json["templateIds"], json["domain_url"], json["domain_secret"])
            tmp_dict["clova_infer"] = clova_result
        set_cost("items", len(clova_result["images"][0]["fields"]))
        set_cost("items-rect", len(clova_result["images"][0]["fields"]))
        convertedWidth = clova_result["images"][0]["convertedImageInfo"]["width"]
        convertedHeight = clova_result["images"][0]["convertedImageInfo"]["height"]
        for field in clova_result["images"][0]["fields"]:
            export_dict[read_id + "." + field["name"]] = field["inferText"]
            ratioBoundingPoly = convert_boundingPoly_to_ratio(
                field["boundingPoly"], convertedWidth, convertedHeight)
            try:
                var_to_rect(read_id + "." + field["name"], ratioBoundingPoly)
            except:
                print("err while var_to_rect")
                import traceback
                traceback.print_exc()
                pass
            try:
                if field["inferText"] == "":
                    if "version" in json and json["version"] != "" and int(json["version"]) > 1:
                        # version 2. get inferText from general if target is null
                        # this is workfround for clova-rect since clova-rect is not good at detecting text
                        print("target is null: " + field["name"])
                        if "clova_general" not in tmp_dict:
                            tmp_dict["clova_general"] = general(image, True)
                        foundFields = find_overlap_fields(
                            tmp_dict["clova_general"], field["boundingPoly"])
                        if len(foundFields) > 0:
                            ff = foundFields[0]
                            widthSimilarity = ff["width_similarity"]
                            heightSimilarity = ff["height_similarity"]
                            if widthSimilarity > 0.5 and widthSimilarity < 1.5 and heightSimilarity > 0.5 and heightSimilarity < 1.5:
                                export_dict[read_id + "." + field["name"]
                                            ] = ff["field"]["inferText"]
            except:
                pass
    elif json["provider"] == "refine":
        refine_strategy = json["strategy"]
        target_key = json["target"]
        override_target = json["overrideTarget"]

        temp_value = target_key
        cur_base = -1
        target_variables = []
        while True:
            value = temp_value
            cur_base += 1
            hasNext = False
            var_keys = re.findall(r'{(.*?)}', value)
            for _var_key in var_keys:
                replace_target_var_key = _var_key
                start_cnt = 0
                var_key = _var_key
                if "," in _var_key:
                    option = _var_key.split(",")[1]
                    if option.split("=")[0] == "start":
                        start_cnt = int(option.split("=")[1])
                    var_key = _var_key.split(",")[0]
                    _var_key = _var_key.split(",")[0]
                # replace all
                # get variable using value
                if "*" in var_key:
                    var_key = var_key.replace("*", str(cur_base + start_cnt))
                if "*" in _var_key and _var_key.replace("*", str(cur_base + start_cnt + 1)) in export_dict:
                    hasNext = True
                if var_key.endswith("_0") and var_key not in export_dict:
                    # values.XXX_0 is not exported
                    # then try to find values.XXX instead
                    var_key = var_key[0:-2]
                if var_key in export_dict:
                    if var_key not in target_variables:
                        target_variables.append(var_key)
                else:
                    # refine target was not found
                    pass
            key_to = "value_" + str(cur_base)
            if not hasNext:
                break
        # now refine
        if refine_strategy == "hand-written-digit":
            target_rects = []
            target_rects_vars = []
            for target_var in target_variables:
                if get_var_to_rect(target_var) != None:
                    target_rects.append(get_var_to_rect(target_var))
                    target_rects_vars.append(target_var)
                    set_cost("items-refine", 1)
            if len(target_rects) != 0:
                result = predicts(image, target_rects)
                for i in range(len(result)):
                    target_var_name = target_rects_vars[i]
                    export_dict[read_id + "." +
                                target_var_name] = result[i]
                    if override_target:
                        export_dict[target_rects_vars[i]] = result[i]
    elif json["provider"] == "logical":
        # =====================
        # Logical
        # =====================
        # get logical result
        script = json["script"]

        def run_script(input_value):
            # just for security reason, input_value should be 100% string
            # script never created from user source. it should be always validated
            # sanitize "`"
            input_value = input_value.replace("`", "\`")
            try:
                # it will throw error if script is not valid
                result = run_js(script.replace(
                    "\"<INPUT_DATA>\"", "`" + input_value + "`"))
                # to string and return
                return result
            except:
                import traceback
                traceback.print_exc()
                return "!ERROR!"

        map = json["input"]
        temp_value = map
        cur_base = -1
        while True:
            value = temp_value
            cur_base += 1
            hasNext = False
            var_keys = re.findall(r'{(.*?)}', value)
            for _var_key in var_keys:
                replace_target_var_key = _var_key
                start_cnt = 0
                var_key = _var_key
                if "," in _var_key:
                    option = _var_key.split(",")[1]
                    if option.split("=")[0] == "start":
                        start_cnt = int(option.split("=")[1])
                    var_key = _var_key.split(",")[0]
                    _var_key = _var_key.split(",")[0]
                # replace all
                # get variable using value
                if "*" in var_key:
                    var_key = var_key.replace("*", str(cur_base + start_cnt))
                if "*" in _var_key and _var_key.replace("*", str(cur_base + start_cnt + 1)) in export_dict:
                    hasNext = True
                if var_key.endswith("_0") and var_key not in export_dict:
                    # values.XXX_0 is not exported
                    # then try to find values.XXX instead
                    var_key = var_key[0:-2]
                if var_key in export_dict:
                    value = value.replace(
                        "{" + replace_target_var_key + "}", export_dict[var_key])
                else:
                    # treat as empty
                    value = value.replace(
                        "{" + replace_target_var_key + "}", "")
            key_to = "value_" + str(cur_base)
            export_dict[read_id + "." + key_to] = run_script(value)
            set_cost("items", 1)
            set_cost("items-logical", 1)
            if not hasNext:
                break
    elif json["provider"] == "openai-gpt" or json["provider"] == "openai-gpt3":
        # =====================
        # OpenAI GPT
        # =====================
        # I think you should make this parallel to be faster
        client = get_openai_client()
        all_text = ""
        i = -1
        cur_base = -1
        while True:
            cur_base += 1
            hasNext = False
            prompt = json["base_prompt"]
            if prompt == "default":
                prompt = default_prompt
            for _key in json["args"]:
                key = "{" + _key + "}"
                value = json["args"][_key]
                # get {VAR}s from value
                var_keys = re.findall(r'{(.*?)}', value)
                for _var_key in var_keys:
                    replace_target_var_key = _var_key
                    start_cnt = 0
                    var_key = _var_key
                    if "," in _var_key:
                        option = _var_key.split(",")[1]
                        if option.split("=")[0] == "start":
                            start_cnt = int(option.split("=")[1])
                        var_key = _var_key.split(",")[0]
                        _var_key = _var_key.split(",")[0]
                    # replace all
                    # get variable using value
                    if "*" in var_key:
                        var_key = var_key.replace(
                            "*", str(cur_base + start_cnt))
                    if "*" in _var_key and _var_key.replace("*", str(cur_base + start_cnt + 1)) in export_dict:
                        hasNext = True
                    if var_key.endswith("_0") and var_key not in export_dict:
                        # values.XXX_0 is not exported
                        # then try to find values.XXX instead
                        var_key = var_key[0:-2]
                    if var_key in export_dict:
                        value = value.replace(
                            "{" + replace_target_var_key + "}", export_dict[var_key])
                    else:
                        # treat as empty
                        value = value.replace(
                            "{" + replace_target_var_key + "}", "")
                prompt = prompt.replace(key, value)
            # completion
            # print("completion...")
            completion_hash = hashlib.md5(prompt.encode()).hexdigest()
            if "completion-" + completion_hash in tmp_dict:
                result = tmp_dict["completion-" + completion_hash]
                total_tokens = tmp_dict["completion-tokens-" + completion_hash]
            else:
                result, total_tokens = completion(
                    prompt, client, json["engine"], user_id)
                tmp_dict["completion-" + completion_hash] = result
                tmp_dict["completion-tokens-" + completion_hash] = total_tokens
            set_cost("natural-tokens", total_tokens)
            if len(result) > 0 and result[0] == '\n':
                result = result[1:]
            if all_text != "":
                all_text += "\n"
            all_text += result
            export_dict[read_id + "." + "text_" + str(cur_base)] = result
            # export to dict
            result_with_cols = result
            if "{COLS}" in json["args"]:
                export_dict[read_id + "." +
                            "csv"] = json["args"]["{COLS}"] + "\n" + result
                result_with_cols = json["args"]["{COLS}"] + "\n" + result
            # export to dict as csv array
            # load text as csv
            csv_reader = csv.DictReader(result_with_cols.strip().splitlines())
            # export to dict
            gpt_is_table = False
            for row in csv_reader:
                gpt_is_table = True
                i += 1
                col_id = -1
                for key, value in row.items():
                    col_id += 1
                    if key == None:
                        key = ""
                    export_dict[read_id + "." + "csv" +
                                "." + key + "_" + str(i)] = value
                    export_dict[read_id + "." + "csv" +
                                ".col_" + str(col_id) + "_" + str(i)] = value
                    set_cost("items", 1)
                    set_cost("items-natural", 1)
            if not gpt_is_table:
                set_cost("items", 1)
                set_cost("items-natural-non-table", 1)
            if not hasNext:
                break
        export_dict[read_id + "." + "text"] = all_text
    elif json["provider"] == "regex":
        # =====================
        # Regex
        # =====================
        # get matched value from input_text and use "regex" for regex, then export to dict
        # get regex
        regex = json["regex"]
        # get matched value
        matched_value = re.findall(regex, input_text)
        print(matched_value)
        # export to dict
        for i in range(len(matched_value)):
            export_dict[read_id + "." + "value_" + str(i)] = matched_value[i]
            set_cost("items", 1)
            set_cost("items-regex", 1)
    elif json["provider"] == "map":
        # =====================
        # Map
        # =====================
        # get values from export_dict that matches with "map" and export to dict
        # if map contains "_*" then it will be treated as wildcard. use range(9999) to find
        # get map
        map = json["map_from"]
        csv_from = json["csv_column_from"]
        csv_to = json["csv_column_to"]
        strategy = json["strategy"]
        csv_data = json["csv_data"]
        normalize = "0"
        if "normalize" in json:
            normalize = json["normalize"]
        if strategy == "ai":
            vectors = json["vectors_data"]
            engine = json["vectors_engine"]
            client = get_openai_client()

        def convert(val):
            if normalize == "1":
                val = unicodedata.normalize("NFKC", val)
            if strategy == "ai":
                if "ai-embedded-" + val in tmp_dict:
                    vector = tmp_dict["ai-embedded-" + val]
                else:
                    vector = embed([val], client, engine, user_id)[0]
                    tmp_dict["ai-embedded-" + val] = vector
                largest = 0
                largest_val = ""
                for vec in vectors:
                    sim = cosine_similarity(vector, vec["vector"])
                    if sim > largest:
                        largest = sim
                        largest_val = vec["data"][csv_to]
                if sim < 0.5:
                    return "!ERROR!"
                return largest_val

            reader = csv.DictReader(csv_data.splitlines())
            for row in reader:
                if strategy == "exact":
                    if row[csv_from] == val:
                        return row[csv_to]
                    elif row[csv_from].strip() == val.strip():
                        return row[csv_to]
                elif strategy == "contains-in-csv":
                    if val in row[csv_from]:
                        return row[csv_to]
                elif strategy == "startswith-csv":
                    if val.startswith(row[csv_from]):
                        return row[csv_to]
                elif strategy == "endswith-csv":
                    if val.endswith(row[csv_from]):
                        return row[csv_to]
                elif strategy == "contains-in-text":
                    if row[csv_from] in val:
                        return row[csv_to]
                elif strategy == "startswith-text":
                    if row[csv_from].startswith(val):
                        return row[csv_to]
                elif strategy == "endswith-text":
                    if row[csv_from].endswith(val):
                        return row[csv_to]
            if strategy == "all":
                reader = csv.DictReader(csv_data.splitlines())
                # 1. exact
                for row in reader:
                    if row[csv_from] == val:
                        return row[csv_to]
                reader = csv.DictReader(csv_data.splitlines())
                # 2. contains-in-csv
                for row in reader:
                    if row[csv_from] in val:
                        return row[csv_to]
                reader = csv.DictReader(csv_data.splitlines())
                # 3. startswith-csv
                for row in reader:
                    if val.startswith(row[csv_from]):
                        return row[csv_to]
                reader = csv.DictReader(csv_data.splitlines())
                # 4. endswith-csv
                for row in reader:
                    if val.endswith(row[csv_from]):
                        return row[csv_to]
                reader = csv.DictReader(csv_data.splitlines())
                # 5. contains-in-text
                for row in reader:
                    if val in row[csv_from]:
                        return row[csv_to]
                reader = csv.DictReader(csv_data.splitlines())
                # 6. startswith-text
                for row in reader:
                    if row[csv_from].startswith(val):
                        return row[csv_to]
                reader = csv.DictReader(csv_data.splitlines())
                # 7. endswith-text
                for row in reader:
                    if row[csv_from].endswith(val):
                        return row[csv_to]
            return "!ERROR!"
        # get matched value
        # check if key is wildcard
        temp_value = map
        cur_base = -1
        while True:
            value = temp_value
            cur_base += 1
            hasNext = False
            var_keys = re.findall(r'{(.*?)}', value)
            for _var_key in var_keys:
                replace_target_var_key = _var_key
                start_cnt = 0
                var_key = _var_key
                if "," in _var_key:
                    option = _var_key.split(",")[1]
                    if option.split("=")[0] == "start":
                        start_cnt = int(option.split("=")[1])
                    var_key = _var_key.split(",")[0]
                    _var_key = _var_key.split(",")[0]
                # replace all
                # get variable using value
                if "*" in var_key:
                    var_key = var_key.replace("*", str(cur_base + start_cnt))
                if "*" in _var_key and _var_key.replace("*", str(cur_base + start_cnt + 1)) in export_dict:
                    hasNext = True
                if var_key.endswith("_0") and var_key not in export_dict:
                    # values.XXX_0 is not exported
                    # then try to find values.XXX instead
                    var_key = var_key[0:-2]
                if var_key in export_dict:
                    value = value.replace(
                        "{" + replace_target_var_key + "}", export_dict[var_key])
                else:
                    # treat as empty
                    value = value.replace(
                        "{" + replace_target_var_key + "}", "")
            key_to = "value_" + str(cur_base)
            export_dict[read_id + "." + key_to] = convert(value)
            set_cost("items", 1)
            set_cost("items-map", 1)
            if not hasNext:
                break
        pass
    else:
        raise Exception("Error: Unknown provider")