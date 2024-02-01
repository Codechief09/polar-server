import hashlib
import json

from firebase_admin import auth, credentials, firestore, storage

from core.gpt_ext import create_embeddings_from_csv


def create_vectors_for_csv_mapping_for_requirements(engine, company_id, master_group_id, master_id, master_historical_id, uid, dry_run=False):
    # get master data
    master = firestore.client().collection(
        f"companies/{company_id}/master_groups/{master_group_id}/masters/{master_id}/master_histories").document(master_historical_id).get().to_dict()

    if master is None:
        master = firestore.client().collection(
            f"companies/{company_id}/master_groups/{master_group_id}/masters/{master_id}/master_histories_staged").document(master_historical_id).get().to_dict()

    # get requirements that have csv columns from firestore
    col = firestore.client().collection(
        f"companies/{company_id}/master_groups/{master_group_id}/masters/{master_id}/master_training_requirements")
    docs = col.stream()
    requirements = []
    for doc in docs:
        target = doc.to_dict()["target_column_name"]
        if target not in requirements:
            requirements.append(target)

    # get file from storage
    bucket = storage.bucket()
    bucket_file_path = master["csv"]["filePath"]
    # get binary from file
    data_bytes = bucket.blob(bucket_file_path).download_as_string()
    # bytes to string
    data_str = data_bytes.decode("utf-8")

    processing_count = 0

    # create vectors
    for req in requirements:
        # saving filename
        name = bucket_file_path + ".prepared/" + \
            hashlib.md5(req.encode()).hexdigest() + ".vectors"

        # check if already exists
        if bucket.blob(name).exists():
            continue

        processing_count += 1

        if dry_run:
            continue

        result = create_embeddings_from_csv(data_str, req, engine, uid)
        dumped = json.dumps(result).encode("utf-8")

        # upload to bucket
        bucket.blob(name).upload_from_string(dumped)

    return processing_count


def load_master_csv_data(reader, db, company_id, staged=False):

    def get_csv_file_name():
        if 'master' in reader:
            master = reader['master']

            if 'id' in master and "groupId" in master:
                master_group_id = master["groupId"]
                master_id = master["id"]

                # find latest master from f"companies/{company_id}/master_groups/{master_group_id}/masters/{master_id}/master_histories"
                # by created_at
                history_sorted = firestore.client().collection(
                    f"companies/{company_id}/master_groups/{master_group_id}/masters/{master_id}/master_histories").order_by('createdAt', direction=firestore.Query.DESCENDING).limit(1).get()

                if staged:
                    history_sorted_staged = firestore.client().collection(
                        f"companies/{company_id}/master_groups/{master_group_id}/masters/{master_id}/master_histories_staged").order_by('createdAt', direction=firestore.Query.DESCENDING).limit(1).get()
                    if len(history_sorted_staged) > 0:
                        if len(history_sorted) == 0:
                            history_sorted = history_sorted_staged
                        else:
                            print("createdAt is: ")
                            print(history_sorted[0].to_dict()['createdAt'])
                            print(history_sorted_staged[0].to_dict()[
                                  'createdAt'])
                            if history_sorted[0].to_dict()['createdAt'] < history_sorted_staged[0].to_dict()['createdAt']:
                                print("staged is bigger: " +
                                      history_sorted_staged[0].id)
                                history_sorted = history_sorted_staged

                if len(history_sorted) > 0:
                    history = history_sorted[0].to_dict()
                    if 'csv' in history:
                        return history['csv']['filePath']

        # NOTE: master が無い場合は、以前の MAP 設定を利用している
        return reader["csv_file_name"]

    # get file from storage
    bucket = storage.bucket()
    bucket_file_path = get_csv_file_name()

    # get binary from file
    data_bytes = bucket.blob(bucket_file_path).download_as_string()

    # bytes to string
    return (bucket_file_path, data_bytes.decode("utf-8"))


def get_ai_csv_path_with_master(master_file_path, column_name):
    return master_file_path + ".prepared/" + \
        hashlib.md5(column_name.encode()).hexdigest() + ".vectors"
