import sys

from OpenSSL import crypto
from twisted.web import server
from twisted.web.resource import Resource
from twisted.web.static import File
from twisted.internet import reactor, ssl
from twisted.internet import endpoints


if __name__ == "__main__":
    root = Resource()
    root.putChild(b'', File('./templates/index.html'))
    root.putChild(b'static', File('./static'))
    site = server.Site(root)

    with open('ca.crt', 'r') as f:
        cert_data = f.read()
    with open('ca.key', 'r') as f:
        key_data = f.read()

    cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_data)
    key = crypto.load_privatekey(crypto.FILETYPE_PEM, key_data)
    options = ssl.CertificateOptions(
        privateKey=key,
        certificate=cert,
        acceptableProtocols=[b'h2'],
    )

    endpoint = endpoints.SSL4ServerEndpoint(reactor, 443, options, backlog=128)
    endpoint.listen(site)
    reactor.run()

    # server = endpoints.serverFromString(
    #     reactor,
    #     "ssl:port=5000:privateKey=ca.key:certKey=ca.crt",
    # )
    # server.listen(site)
    # reactor.run()
