# detect Ctrl + C
import signal
import time
from threading import Thread

import firebase_admin
from firebase_admin import firestore

import batch_operation
import firebase_initializer
from variables import get_storage_bucket_name

exit_requested = False
error_thrown = False
firestore_uploaded_updated = False
firestore_converted_updated = False


# init firebase if not initialized
if not firebase_admin.initialize_app:
    firebase_admin.initialize_app(
        options={'storageBucket': get_storage_bucket_name()})


def signal_handler(sig, frame):
    global exit_requested
    print('You pressed Ctrl+C. trying to exit...')
    exit_requested = True


def signal_handler_term(sig, frame):
    global exit_requested
    print('trying to exit...')
    exit_requested = True


def check_if_exception_requires_restart(exception):
    if exception is None:
        return False
    if "_UnaryStreamMultiCallable" in str(exception):
        return True
    if "DeadlineExceeded" in str(exception) and "google" in str(exception):
        return True
    if "_MultiThreadedRendezvous" in str(exception) and "grpc" in str(exception):
        return True
    if "has no attribute '_retry'" in str(exception):
        return True
    return False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler_term)


def watch_firebase_updates():
    global exit_requested
    try:
        def on_snapshot_uploaded(doc_snapshot, changes, read_time):
            global firestore_uploaded_updated
            for doc in doc_snapshot:
                print("[uploaded] UPDATED")
                firestore_uploaded_updated = True

        def on_snapshot_converted(doc_snapshot, changes, read_time):
            global firestore_converted_updated
            for doc in doc_snapshot:
                print("[converted] UPDATED")
                firestore_converted_updated = True

        collection = firestore.client().collection("ope")
        # watch document changes
        # uploaded
        doc_ref = collection.document("uploaded_update_to_detected")
        doc_watch_uploaded = doc_ref.on_snapshot(on_snapshot_uploaded)
        # converted
        doc_ref = collection.document("converted_add")
        doc_watch_converted = doc_ref.on_snapshot(on_snapshot_converted)
        while not exit_requested:
            time.sleep(10)
            if doc_watch_uploaded._closed:
                print("[uploaded] re-registering firestore watcher...")
                doc_watch_uploaded = doc_ref.on_snapshot(on_snapshot_uploaded)
            if doc_watch_converted._closed:
                print("[converted] re-registering firestore watcher...")
                doc_watch_converted = doc_ref.on_snapshot(
                    on_snapshot_converted)
    except:
        import traceback
        traceback.print_exc()
        print("error thrown by watch_firebase_updates")
        global error_thrown
        error_thrown = True
        raise


def operate_detected_items():
    global error_thrown
    global exit_requested
    global firestore_uploaded_updated
    typ = "detected"
    try:
        while not exit_requested:
            if exit_requested:
                print("exit requested.")
                break
            print("[detected] start processing...")
            operated_count, err, exception = batch_operation.deal_uploaded_data_random(
                typ)
            print("[detected] Operated count: " + str(operated_count))
            if err != "" and operated_count > 0:
                print("[detected] Error while processing, sleep 10 seconds...")
                if check_if_exception_requires_restart(exception):
                    print("exception requires restart. restarting...")
                    print(exception)
                    error_thrown = True
                    break
                time.sleep(10)
            if exit_requested:
                print("exit requested.")
                break
            if operated_count == 0:
                print("[detected] sleeping...")
                for i in range(60):
                    time.sleep(1)
                    if exit_requested:
                        print("exit requested.")
                        break
                    if firestore_uploaded_updated:
                        print("[detected] firestore updated. trying to check...")
                        firestore_uploaded_updated = False
                        break
    except:
        import traceback
        traceback.print_exc()
        print("error thrown by operate_detected_items")
        error_thrown = True
        raise


def operate_converted_items():
    global error_thrown
    global exit_requested
    global firestore_converted_updated
    try:
        while not exit_requested:
            if exit_requested:
                print("exit requested.")
                break
            print("[converted] start processing...")
            operated_count, err, exception = batch_operation.deal_converted_data_random()
            print("[converted] Operated count: " + str(operated_count))
            if err != "" and operated_count > 0:
                print("[converted] Error while processing, sleep 10 seconds...")
                if check_if_exception_requires_restart(exception):
                    print("exception requires restart. restarting...")
                    print(exception)
                    error_thrown = True
                    break
                time.sleep(10)
            if exit_requested:
                print("exit requested.")
                break
            if operated_count == 0:
                print("[converted] sleeping")
                for i in range(60):
                    time.sleep(1)
                    if exit_requested:
                        print("exit requested.")
                        break
                    if firestore_converted_updated:
                        print("[converted] firestore updated. trying to check...")
                        firestore_converted_updated = False
                        break
    except:
        import traceback
        traceback.print_exc()
        print("error thrown by operate_converted_items")
        error_thrown = True
        raise


if __name__ == "__main__":
    print("version: v1.0.2")
    th1 = Thread(target=operate_detected_items, args=())
    th2 = Thread(target=operate_converted_items, args=())
    th3 = Thread(target=watch_firebase_updates, args=())
    th1.start()
    th2.start()
    th3.start()
    while not exit_requested and not error_thrown:
        time.sleep(1)
    exit_requested = True
    th1.join()
    th2.join()
    th3.join()
