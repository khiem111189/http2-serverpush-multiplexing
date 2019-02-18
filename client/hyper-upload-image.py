from hyper import HTTP20Connection
from hyper import http20
import time
from urllib3.fields import RequestField
from urllib3.filepost import encode_multipart_formdata
import sys
import os
import mimetypes
import ntpath
import json
from array import *

file_path = sys.argv[1]

file_size = os.stat(file_path).st_size

# We can now open the file.
file = open(file_path, "rb")
try:
    fileobj = file.read()
finally:
    file.close()

conn = HTTP20Connection('localhost2:443', force_proto='h2', enable_push=True)
content_type, content_encoding = mimetypes.guess_type(file_path)
rf = RequestField(name='file', data=fileobj, filename=ntpath.basename(file_path))
rf.make_multipart(content_type=content_type)
body, content_type = encode_multipart_formdata([rf])
fileobj = body

request_headers = {
            'content-length': str(file_size),
            # 'content-type': content_type
            'content-type': 'application/json'
        }

conn.request('POST', '/upload', body=json.dumps({'file': 'file'}), headers=request_headers)
response = conn.get_response()
print(response)
# print(resp.read())