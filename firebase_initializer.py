import firebase_admin

from variables import get_storage_bucket_name

# init firebase if not initialized
if not firebase_admin._apps:
    firebase_admin.initialize_app(
        options={'storageBucket': get_storage_bucket_name()})
