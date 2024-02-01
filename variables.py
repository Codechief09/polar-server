import os


def get_clova_api_url():
    api_base_url = os.environ.get('CLOVA_API_URL')
    api_url = api_base_url + '/general'
    return api_url


def get_clova_infer_api_url():
    api_base_url = os.environ.get('CLOVA_API_URL')
    api_url = api_base_url + '/infer'
    return api_url


def get_clova_secret_key():
    secret_key = os.environ.get('CLOVA_SECRET_KEY')
    return secret_key


def get_clova_infer_secret_key():
    return get_clova_secret_key()


def get_gpt_api_key():
    return os.environ.get('OPENAI_KEY')


def get_storage_bucket_name():
    bucket_name = os.environ.get('STORAGE_BUCKET_NAME')
    return bucket_name


def get_gcp_project_id():
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project_id is None or project_id == "":
        project_id = "battonaiocr-staging"
    return project_id


def get_gcp_location():
    # TODO: fix me
    return "asia-northeast1"


def get_vertex_ocr_endpoint_name_prefix():
    # TODO: fix me
    return "trocr-handwritten"
