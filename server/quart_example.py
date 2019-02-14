import ssl
import os, glob
import uuid
from io import BytesIO
import asyncio
from PIL import Image
import json
from hypercorn.asyncio import serve
from hypercorn.config import Config as HyperConfig
from typing import (
    Any, AnyStr, Callable, cast, Dict, Iterable, List, Optional, Set, Tuple, Union, ValuesView,
)

from quart import (
    abort, jsonify, make_response, Quart, render_template, request, redirect, url_for, send_file, logging
)

app = Quart(__name__)

user_folder = 'data'
user_images_folder = 'data/images'

user_data = json.dumps({})

@app.route('/')
async def index():
    result = await render_template('index.html',
            username=user_data["name"], images=user_data["images"])
    response = await make_response(result)
    response.push_promises.update([
        url_for('static', filename='css/bootstrap.min.css'),
        url_for('static', filename='js/bootstrap.min.js'),
        url_for('static', filename='js/jquery.min.js')
    ])
    response.push_promises.add(url_for('get_data_images', filename='test4.jpg'))
    return response

@app.route('/img')
async def image():
    result = await render_template('img.html',
            username=user_data["name"], images=user_data["images"])
    response = await make_response(result)
    response.push_promises.update([
        url_for('static', filename='css/bootstrap.min.css'),
        url_for('static', filename='js/bootstrap.min.js'),
        url_for('static', filename='js/jquery.min.js')
    ])
    # response.push_promises.add(url_for('get_data_images', filename='test4.jpg'))
    return response

@app.route('/upload', methods=['POST'])
async def upload_post():
    uploads = await request.files
    print(uploads)
    file = uploads['file']
    if file.filename == '':
        return redirect(url_for('index'))
    filename = file.filename
    image_id = str(uuid.uuid4())
    filename = image_id + filename
    for image in user_data['images']:
        if image['filename'] == filename:
           filename = image_id + filename
           break
    print(filename)
    user_data['images'].append({
        "imageId": image_id,
        "filename": filename,
        "tags": []
    })
    file.save(os.path.join(user_images_folder, filename))

    print(json.dumps(user_data))

    return redirect(url_for('index'))

@app.route('/addTag', methods=['POST'])
async def add_tag():
    form = await request.form
    print(form)
    imageId = form['imageId']
    tag = form['tag']
    if tag == '':
        return redirect(url_for('index'))
    searchedImage = {}
    for image in user_data['images']:
        if image['imageId'] == imageId:
            searchedImage = image
            break
    searchedImage['tags'].append(tag)    
    print(json.dumps(user_data))
    return redirect(url_for('index'))


@app.route('/data/images/<string:filename>', methods=['GET'])
async def get_data_images(filename):
    return await send_file(user_images_folder + '/' + filename, conditional=True)

@app.route("/mp")
async def mp():
    result = await render_template('multiplex.html')
    response = await make_response(result)
    response.push_promises.update([
        url_for('static', filename='css/bootstrap.min.css'),
        url_for('static', filename='js/bootstrap.min.js'),
        url_for('static', filename='js/jquery.min.js')
    ])
    return response

@app.route('/multiplex/<int:req_id>', methods=['GET'])
async def test_multiplex(req_id):
    await asyncio.sleep(1)
    return jsonify({"key": "value %d" % req_id})

def run(
        quart,
        host: str='127.0.0.1',
        port: int=5000,
        debug: Optional[bool]=None,
        use_reloader: bool=True,
        loop: Optional[asyncio.AbstractEventLoop]=None,
        ca_certs: Optional[str]=None,
        certfile: Optional[str]=None,
        keyfile: Optional[str]=None,
        **kwargs: Any,
) -> None:
    """Run this application.

    This is best used for development only, see Hypercorn for
    production servers.

    Arguments:
        host: Hostname to listen on. By default this is loopback
            only, use 0.0.0.0 to have the server listen externally.
        port: Port number to listen on.
        debug: If set enable (or disable) debug mode and debug output.
        use_reloader: Automatically reload on code changes.
        loop: Asyncio loop to create the server in, if None, take default one.
            If specified it is the caller's responsibility to close and cleanup the
            loop.
        ca_certs: Path to the SSL CA certificate file.
        certfile: Path to the SSL certificate file.
        ciphers: Ciphers to use for the SSL setup.
        keyfile: Path to the SSL key file.

    """
    if kwargs:
        warnings.warn(
            f"Additional arguments, {','.join(kwargs.keys())}, are not supported.\n"
            "They may be supported by Hypercorn, which is the ASGI server Quart "
            "uses by default. This method is meant for development and debugging."
        )

    config = HyperConfig()
    # config.alpn_protocols = ["http/1.1"]
    config.alpn_protocols = ["h2"]
    config.access_log_format = "%(h)s %(r)s %(s)s %(b)s %(D)s"
    config.access_logger = logging.create_serving_logger()  # type: ignore
    config.bind = [f"{host}:{port}"]
    config.ca_certs = ca_certs
    config.certfile = certfile
    if debug is not None:
        config.debug = debug
    config.error_logger = config.access_logger  # type: ignore
    config.keyfile = keyfile
    config.use_reloader = use_reloader

    scheme = 'https' if config.ssl_enabled else 'http'
    print("Running on {}://{} (CTRL + C to quit)".format(scheme, config.bind[0]))  # noqa: T001

    if loop is not None:
        loop.set_debug(config.debug)
        loop.run_until_complete(serve(quart, config))  # type: ignore
    else:
        asyncio.run(serve(quart, config), debug=config.debug)  # type: ignore

if __name__ == '__main__':
    # for f in glob.glob(user_images_folder + "/*"):
    #     os.remove(f)
    with open('data/user.json') as f:
        user_data = json.load(f)
    run(app, host='localhost2', port=443, certfile='ca2.crt', keyfile='ca2.key')

    # ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    # ssl_context.options |= (
    #     ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_COMPRESSION
    # )
    # ssl_context.set_ciphers("ECDHE+AESGCM")
    # ssl_context.load_cert_chain(certfile="ca.crt", keyfile="ca.key")
    # ssl_context.set_alpn_protocols(["h2"])

    # loop = asyncio.get_event_loop()
    # # Each client connection will create a new protocol instance
    # coro = loop.create_server(H2Protocol, 'localhost', 443, ssl=ssl_context)
    # server = loop.run_until_complete(coro)

    # ssl_context = ssl.create_default_context(
    #     ssl.Purpose.CLIENT_AUTH,
    # )
    # ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
    # ssl_context.set_ciphers('ECDHE+AESGCM')
    # ssl_context.load_cert_chain(
    #     certfile='ca.crt', keyfile='ca.key',
    # )
    # ssl_context.set_alpn_protocols(['h2', 'http/1.1'])

    # app.run(host='localhost', port=443, certfile='ca.crt', keyfile='ca.key')

    # ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    # ssl_context.options |= (
    #     ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_COMPRESSION
    # )
    # ssl_context.set_ciphers("ECDHE+AESGCM")
    # ssl_context.load_cert_chain(certfile="ca.crt", keyfile="ca.key")
    # ssl_context.set_alpn_protocols(["h2"])

    # loop = asyncio.get_event_loop()
    # # Each client connection will create a new protocol instance
    # coro = loop.create_server(Quart, 'localhost', 443, ssl=ssl_context)
    # server = loop.run_until_complete(coro)

    # # Serve requests until Ctrl+C is pressed
    # print('Serving on {}'.format(server.sockets[0].getsockname()))
    # try:
    #     loop.run_forever()
    # except KeyboardInterrupt:
    #     pass

    # # Close the server
    # server.close()
    # loop.run_until_complete(server.wait_closed())
    # loop.close()


