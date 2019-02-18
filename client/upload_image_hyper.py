import requests
import sys
import os
from hyper.contrib import HTTP20Adapter

def upload_image(image_path):
         
    image_filename = os.path.basename(image_path)
 
    multipart_form_data = {
        'file': (image_filename, open(image_path, 'rb'))
    }

    s = requests.Session()
    s.mount('https://localhosts', HTTP20Adapter())
 
    response = requests.post('https://localhost2/upload',
                             files=multipart_form_data)
 
    print(response.status_code)

upload_image(sys.argv[1])
