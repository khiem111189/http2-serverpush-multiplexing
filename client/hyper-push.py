from hyper import HTTP20Connection
from hyper import http20
import time

conn = HTTP20Connection('localhost2:443', force_proto='h2', enable_push=True)
conn.request('GET', '/')
response = conn.get_response()
for push in conn.get_pushes(): # all pushes promised before response headers
    print(push.path)

# print(resp.read())