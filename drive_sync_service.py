import time
import servicemanager
import win32event
import win32service
import win32serviceutil
import logging
import os
import traceback

# Import your main sync script
import enhanced_auto_sync_to_drive

# Set up logging for the service
SERVICE_LOG_FILE = os.path.join(r'C:\Users\Nathan\Downloads\google drive uploader bat', 'service_log.log')
logging.basicConfig(
    filename=SERVICE_LOG_FILE,
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

class GoogleDriveSyncService(win32serviceutil.ServiceFramework):
    _svc_name_ = "GoogleDriveSyncService"
    _svc_display_name_ = "Google Drive Sync Service"
    _svc_description_ = "Automatically syncs local folder with Google Drive continuously."

    def __init__(self, args):
        super().__init__(args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        logging.info('Service is stopping...')
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.running = False
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        logging.info('Service is starting...')
        try:
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            enhanced_auto_sync_to_drive.main()
        except Exception as e:
            logging.error(f'Exception in SvcDoRun: {e}')
            logging.error(traceback.format_exc())
            self.SvcStop()

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(GoogleDriveSyncService)
