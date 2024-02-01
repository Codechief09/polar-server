import csv
import re


def workflow_export(json, export_dict, export_csv_str, raw_map=dict()):
    result = []
    reader = csv.reader(export_csv_str.splitlines())
    for row in reader:
        # find row count
        row_count = 1
        for col in row:
            var_keys = re.findall(r'{(.*?)}', col)
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
                if "*" in var_key:
                    for i in range(9999):
                        target = var_key.replace("*", str(i + start_cnt))
                        if target.endswith("_0") and target not in export_dict:
                            # values.XXX_0 is not exported
                            # then try to find values.XXX instead
                            target = target[0:-2]
                        if target in export_dict and row_count < i + 1:
                            row_count = i + 1
        # create rows
        rows = []
        for _ in range(row_count):
            cur_arr = []
            for _ in range(len(row)):
                cur_arr.append("")
            rows.append(cur_arr)
        # create cells in rows
        for i in range(len(row)):
            col = row[i]
            var_keys = re.findall(r'{(.*?)}', col)
            for j in range(row_count):
                target_data = col
                tmp_target_var_key = ""
                tmp_target_var_key_raw = col
                for _var_key in var_keys:
                    replace_target_var_key = _var_key
                    start_cnt = 0
                    var_key = _var_key
                    enable_numeric = False
                    if "," in _var_key:
                        if "numeric" in _var_key.split(",")[1:]:
                            enable_numeric = True
                        option = _var_key.split(",")[1]
                        if option.split("=")[0] == "start":
                            start_cnt = int(option.split("=")[1])
                        var_key = _var_key.split(",")[0]
                        _var_key = _var_key.split(",")[0]
                    # replace
                    target = var_key.replace("*", str(j + start_cnt))
                    if target.endswith("_0") and target not in export_dict:
                        # values.XXX_0 is not exported
                        # then try to find values.XXX instead
                        target = target[0:-2]
                    if target in export_dict and export_dict[target] != None:
                        # tmp data for the reference
                        tmp_target_var_key = target
                        exported = export_dict[target]
                        if enable_numeric:
                            exported = exported.replace("!", "1")
                            exported = exported.replace("！", "1")
                            exported = exported.replace("|", "1")
                            exported = exported.replace("｜", "1")
                            exported = exported.replace("」", "1")
                            exported = exported.replace("「", "1")
                            exported = exported.replace("/", "1")
                            exported = exported.replace("／", "1")
                            exported = exported.replace("o", "0")
                            exported = exported.replace("O", "0")
                            exported = exported.replace("〇", "0")
                            exported = exported.replace("ー", "-")
                            exported = exported.replace("―", "-")
                        target_data = target_data.replace(
                            "{" + replace_target_var_key + "}", exported)
                    else:
                        target_data = target_data.replace(
                            "{" + replace_target_var_key + "}", "")
                rows[j][i] = target_data
                # set tmp data for the reference
                raw_map[str(j) + "_" + str(i)] = tmp_target_var_key
                raw_map[str(j) + "_" + str(i) +
                        "_raw"] = tmp_target_var_key_raw
            """
            if "_*" in col:
                for j in range(row_count):
                    target = col.replace("_*", "_" + str(j))
                    if target in export_dict:
                        rows[j][i] = export_dict[target]
            else:
                for j in range(row_count):
                    if col in export_dict:
                        rows[j][i] = export_dict[col]
                    else:
                        rows[j][i] = col
            """
        # append rows
        result += rows
    return result
