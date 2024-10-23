import os
import io
import time
import logging
import ssl
import psutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# OAuth 2.0 Scopes for Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive']

# Paths Configuration
SCRIPT_DIR = r'C:\Users\Nathan\Downloads\google drive uploader bat'
LOCAL_FOLDER = r'C:\Users\Nathan\OneDrive\OneDriveLAPTOPCloudDownloads'
DRIVE_FOLDER_ID = '1pMaLxGCBpQTj8qncccvgI06H7Pd0u28I'
CREDENTIALS_PATH = os.path.join(SCRIPT_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(SCRIPT_DIR, 'token.json')
LOG_FILE = os.path.join(SCRIPT_DIR, 'sync_log.log')

# Excluded Files from Deletion
EXCLUDED_FILES = [
    'credentials.json',
    'token.json',
    'drive_sync_service.py',
    'enhanced_auto_sync_to_drive.py',
    'sync_log.log',
    'service_log.log'
]

# Set up logging
logging.basicConfig(
    filename=LOG_FILE,
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

def authenticate_drive_api():
    """Authenticate with Google Drive API using OAuth 2.0."""
    creds = None
    try:
        if os.path.exists(TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Use secure SSL context
                ssl_context = ssl.create_default_context()
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                creds = flow.run_local_server(port=0, ssl_context=ssl_context)
            
            # Save the token for future use
            with open(TOKEN_PATH, 'w') as token_file:
                token_file.write(creds.to_json())
        
        logging.info("Successfully authenticated with Google Drive.")
    except Exception as e:
        logging.error(f"Failed to authenticate with Google Drive: {str(e)}")
        raise e

    return build('drive', 'v3', credentials=creds)

def upload_file(service, file_path, drive_folder_id):
    """Upload a file to Google Drive."""
    try:
        file_name = os.path.basename(file_path)
        file_metadata = {'name': file_name, 'parents': [drive_folder_id]}
        media = MediaFileUpload(file_path, resumable=True)
        request = service.files().create(body=file_metadata, media_body=media, fields='id')
        response = None

        while response is None:
            status, response = request.next_chunk(num_retries=5)
            if status:
                logging.info(f"Uploaded {file_name} ({int(status.progress() * 100)}%)")
        logging.info(f"Uploaded {file_name} to Google Drive (ID: {response.get('id')})")
    except ssl.SSLError as ssl_error:
        logging.error(f"SSL error while uploading {file_name}: {str(ssl_error)}")
    except Exception as e:
        logging.error(f"Failed to upload {file_name}: {str(e)}")

def download_file(service, file_id, file_name, local_folder):
    """Download a file from Google Drive."""
    try:
        request = service.files().get_media(fileId=file_id)
        file_path = os.path.join(local_folder, file_name)
        with io.FileIO(file_path, 'wb') as file:
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while not done:
                status, done = downloader.next_chunk(num_retries=5)
                if status:
                    logging.info(f"Downloaded {file_name} ({int(status.progress() * 100)}%)")
        logging.info(f"Downloaded {file_name} to local folder.")
    except ssl.SSLError as ssl_error:
        logging.error(f"SSL error while downloading {file_name}: {str(ssl_error)}")
    except Exception as e:
        logging.error(f"Failed to download {file_name}: {str(e)}")

def delete_drive_file(service, file_id):
    """Delete a file from Google Drive."""
    try:
        service.files().delete(fileId=file_id).execute()
        logging.info(f"Deleted file with ID {file_id} from Google Drive.")
    except Exception as e:
        logging.error(f"Failed to delete file with ID {file_id}: {str(e)}")

def is_file_in_use(file_path):
    """Check if a file is currently in use by another process."""
    for proc in psutil.process_iter(['open_files']):
        try:
            open_files = proc.info['open_files'] or []
            for open_file in open_files:
                if open_file.path == file_path:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def sync_drive_to_local(service, drive_folder_id, local_folder):
    """Sync files from Google Drive to the local folder."""
    try:
        results = service.files().list(
            q=f"'{drive_folder_id}' in parents and trashed=false",
            fields="files(id, name)"
        ).execute()
        drive_files = results.get('files', [])
        local_files = os.listdir(local_folder)

        # Download missing files from Google Drive
        for drive_file in drive_files:
            if drive_file['name'] not in local_files:
                download_file(service, drive_file['id'], drive_file['name'], local_folder)

        # Delete extra local files not present in Google Drive
        for local_file in local_files:
            if (local_file not in [f['name'] for f in drive_files]) and (local_file not in EXCLUDED_FILES):
                local_file_path = os.path.join(local_folder, local_file)
                if not is_file_in_use(local_file_path):
                    os.remove(local_file_path)
                    logging.info(f"Deleted {local_file} from local folder.")
                else:
                    logging.warning(f"Cannot delete {local_file} as it is currently in use.")
    except Exception as e:
        logging.error(f"Error syncing Drive to local: {str(e)}")

class LocalFolderEventHandler(FileSystemEventHandler):
    """Handle local folder changes and sync with Google Drive."""
    def __init__(self, service, drive_folder_id):
        self.service = service
        self.drive_folder_id = drive_folder_id

    def on_modified(self, event):
        if not event.is_directory:
            logging.info(f"Detected modification: {event.src_path}")
            upload_file(self.service, event.src_path, self.drive_folder_id)

    def on_created(self, event):
        if not event.is_directory:
            logging.info(f"Detected new file: {event.src_path}")
            upload_file(self.service, event.src_path, self.drive_folder_id)

    def on_deleted(self, event):
        if not event.is_directory:
            logging.info(f"Detected deletion: {event.src_path}")
            file_name = os.path.basename(event.src_path)
            self.delete_file_from_drive(file_name)

    def delete_file_from_drive(self, file_name):
        try:
            results = self.service.files().list(
                q=f"name='{file_name}' and '{self.drive_folder_id}' in parents",
                fields="files(id, name)"
            ).execute()
            drive_files = results.get('files', [])
            if drive_files:
                delete_drive_file(self.service, drive_files[0]['id'])
            else:
                logging.warning(f"No matching file found in Drive for deletion: {file_name}")
        except Exception as e:
            logging.error(f"Failed to delete {file_name} from Google Drive: {str(e)}")

def main():
    """Main function to authenticate and start syncing."""
    try:
        service = authenticate_drive_api()
    except Exception as e:
        logging.critical(f"Authentication failed: {str(e)}")
        return

    event_handler = LocalFolderEventHandler(service, DRIVE_FOLDER_ID)
    observer = Observer()
    observer.schedule(event_handler, path=LOCAL_FOLDER, recursive=True)
    observer.start()
    logging.info("Started monitoring local folder for changes.")

    try:
        while True:
            sync_drive_to_local(service, DRIVE_FOLDER_ID, LOCAL_FOLDER)
            time.sleep(60)  # Sync every 60 seconds
    except KeyboardInterrupt:
        observer.stop()
        logging.info("Stopping observer due to keyboard interrupt.")
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        observer.stop()
    observer.join()

if __name__ == '__main__':
    main()
