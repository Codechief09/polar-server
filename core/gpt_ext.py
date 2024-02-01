import csv
from core.gpt import embed, embed_grouped_by_1024
import numpy as np
from core.openai_client import get_openai_client

def cos_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def create_embeddings_from_csv(csv_data, col, engine, user_id):
    reader = csv.DictReader(csv_data.splitlines(), delimiter=',')
    # check if col exists
    if col not in reader.fieldnames:
        return []
    result = []
    targets = []
    for row in reader:
        data = row[col]
        if data != "" and data not in targets:
            targets.append(data)
            result.append({
                "data": row,
            })
    client = get_openai_client()
    embedded = embed_grouped_by_1024(targets, client, engine, user_id)

    for i in range(len(embedded)):
        result[i]["vector"] = embedded[i]

    return result


def cosine_similarity(a, b):
    return cos_sim(a, b)
