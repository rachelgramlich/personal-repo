import gspread
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# Load or obtain OAuth credentials
creds = None

# The file token.json will store the user's access and refresh tokens after authorization.
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)

# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=8000)
    # Save the credentials for the next run
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

# Authorize access to Google Sheets
gc = gspread.authorize(creds)

# Accessing the sheet by title
spreadsheet = gc.open('Grocery Wizard Automation') #Replace with the name of your gsheet
worksheet = spreadsheet.worksheet('Links')  # Replace with the name of your worksheet

# Example: Read data from cell A1
cell_value = worksheet.acell('A1').value
print(f'Value: {cell_value}')
