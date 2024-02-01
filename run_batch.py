# detect Ctrl + C
import signal
import time

import batch_operation

exit_requested = False


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
    if "DeadlineExceeded" in str(exception):
        return True
    if "_MultiThreadedRendezvous" in str(exception):
        return True
    if "has no attribute '_retry'" in str(exception):
        return True
    return False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler_term)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python run_batch.py type")
        print("Type: `detected`, `uploaded`, `extracted` or `converted`")
        sys.exit(1)
    typ = sys.argv[1]
    if typ == "detected" or typ == "uploaded" or typ == "extracted":
        while True:
            if exit_requested:
                print("exit requested.")
                break
            print("start processing... [" + typ + "]")
            operated_count, err, exception = batch_operation.deal_uploaded_data_random(
                typ)
            if check_if_exception_requires_restart(exception):
                print("exception requires restart. restarting...")
                print(exception)
                break
            print("Operated count: " + str(operated_count))
            if exit_requested:
                print("exit requested.")
                break
            if operated_count == 0:
                print("sleeping...")
                for i in range(10):
                    time.sleep(1)
                    if exit_requested:
                        print("exit requested.")
                        break
    elif typ == "converted":
        while True:
            if exit_requested:
                print("exit requested.")
                break
            print("start processing... [converted]")
            operated_count, err, exception = batch_operation.deal_converted_data_random()
            if check_if_exception_requires_restart(exception):
                print("exception requires restart. restarting...")
                print(exception)
                break
            print("Operated count: " + str(operated_count))
            if exit_requested:
                print("exit requested.")
                break
            if operated_count == 0:
                print("sleeping")
                for i in range(10):
                    time.sleep(1)
                    if exit_requested:
                        print("exit requested.")
                        break
