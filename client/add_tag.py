import requests
import os
import sys
 
def add_tag(image_id, tag_value):
         
    payload = {'imageId': image_id, 'tag': tag_value}
 
 
    response = requests.post('https://localhost2/addTag',data=payload)
 
    print(response.status_code)

add_tag(sys.argv[1], sys.argv[2])