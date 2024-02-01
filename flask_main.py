from flask import Flask, g, request
from flask_cors import CORS

import main as funcs
from pkg.config.main import API_VERSION
from pkg.logging.main import LoggerLevel, custom_log

app = Flask(__name__)

CORS(app)


# perform


@app.route("/perform_general_ocr", methods=["POST", "OPTIONS"])
def main_perform_general_ocr():
    return funcs.perform_general_ocr(request)


@app.route("/auto_rotate_image", methods=["POST", "OPTIONS"])
def main_auto_rotate_image():
    return funcs.auto_rotate_image(request)


@app.route("/pdf_to_image", methods=["POST", "OPTIONS"])
def main_pdf_to_image():
    return funcs.pdf_to_image(request)


@app.route("/read", methods=["POST", "OPTIONS"])
def main_run_read():
    return funcs.run_read(request)


@app.route("/read_one", methods=["POST", "OPTIONS"])
def main_run_read_one():
    return funcs.run_read_one(request)


@app.route("/write", methods=["POST", "OPTIONS"])
def main_run_write():
    return funcs.run_write(request)


@app.route("/match", methods=["POST", "OPTIONS"])
def main_run_get_matched_template_id():
    return funcs.run_get_matched_template_id(request)


@app.route("/add_master_training_requirement", methods=["POST", "OPTIONS"])
def main_add_master_training_requirement():
    return funcs.add_master_training_requirement(request)


@app.route("/create_vectors_for_csv_mapping_to_satisfy_requirement", methods=["POST", "OPTIONS"])
def main_create_vectors_for_csv_mapping_to_satisfy_requirement():
    return funcs.create_vectors_for_csv_mapping_to_satisfy_requirement(request)


@app.route("/check_if_vectorizing_required_for_the_master", methods=["POST", "OPTIONS"])
def main_check_if_vectorizing_required_for_the_master():
    return funcs.check_if_vectorizing_required_for_the_master(request)


@app.route("/create_vectors_for_csv_mapping", methods=["POST", "OPTIONS"])
def main_create_vectors_for_csv_mapping():
    return funcs.create_vectors_for_csv_mapping(request)


@app.route("/deal_uploaded_data_with_ids", methods=["POST", "OPTIONS", "GET"])
def main_deal_uploaded_data_with_ids():
    return funcs.deal_uploaded_data_with_ids(request)


@app.route("/create_script_from_prompt", methods=["POST", "OPTIONS", "GET"])
def main_create_script_from_prompt():
    return funcs.create_script_from_prompt(request)


@app.route("/version")
def main_check_api_version():
    return {"version": API_VERSION}


@app.route("/test")
def main_test():
    print("started")
    import time
    time.sleep(3)
    return ""


@app.route("/health")
def main_health():
    return funcs.health()


# @app.before_request
# def before_request() -> None:
#     """
#     ログ出すために必要な開始時間とトレースidをリクエスト時に取得
#     """
#     g.start = time.time()
#     # Cloud RunのヘッダーからトレースIDを取得
#     g.trace_id = request.headers.get('X-Cloud-Trace-Context').split('/')[
#         0] if 'X-Cloud-Trace-Context' in request.headers else None
#
#
# @app.after_request
# def log_request(response) -> None:
#     """
#     リクエスト終わった後ログ取得
#     """
#     # Get the current time
#     now = time.time()
#
#     # Calculate the request duration
#     duration = round(now - g.start, 2)
#
#     # Get the request parameters and path
#     params = request.args.to_dict()
#     request_path = request.path
#     log_message = f"""
#         Request to {request_path} with parameters {params}, Response: {str(response.data, 'utf-8')},
#         Request duration: {duration} seconds.
#         """
#     # 3. ログを出力
#     custom_log(log_message)
#     return response


@app.errorhandler(500)
def handle_500(error):
    """
    500エラーが出た時にトレースバック付きでログを出力
    """
    custom_log(
        f"An internal error occurred: {error}", level=LoggerLevel.CRITICAL, exc_info=True)
    return str(error), 500


if __name__ == "__main__":
    # get port from argument
    import sys

    port = 8080
    print("initializing polar... [" + "v1.7.0" + "]")
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
        print(port)
    app.run(port=port, debug=True)
