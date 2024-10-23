from __future__ import print_function
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Define the OAuth 2.0 scopes for the Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive']

# Authenticate and authorize the Google Drive API
def authenticate_drive_api():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

# Upload files from the local folder to the Google Drive folder
def upload_files(service, local_folder, drive_folder_id):
    for root, dirs, files in os.walk(local_folder):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            file_metadata = {
                'name': file_name,
                'parents': [drive_folder_id]
            }
            media = MediaFileUpload(file_path, resumable=True)
            request = service.files().create(body=file_metadata, media_body=media, fields='id')
            response = request.execute()
            print(f"Uploaded {file_name} to Google Drive (ID: {response.get('id')})")

if __name__ == '__main__':
    # Authenticate and get the Google Drive service
    service = authenticate_drive_api()

    # Define the local folder path and Google Drive folder ID
    local_folder = r'C:\Users\Nathan\OneDrive\OneDriveLAPTOPCloudDownloads'  # Replace with your local folder path
    drive_folder_id = '1pMaLxGCBpQTj8qncccvgI06H7Pd0u28I'  # Google Drive folder ID

    # Upload files from the local folder to Google Drive
    upload_files(service, local_folder, drive_folder_id)
