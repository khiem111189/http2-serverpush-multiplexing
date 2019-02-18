# -*- coding: utf-8 -*-
"""
post_request.py
~~~~~~~~~~~~~~~

A short example that demonstrates a client that makes POST requests to certain
websites.

This example is intended to demonstrate how to handle uploading request bodies.
In this instance, a file will be uploaded. In order to handle arbitrary files,
this example also demonstrates how to obey HTTP/2 flow control rules.

Takes one command-line argument: a path to a file in the filesystem to upload.
If none is present, uploads this file.
"""
from __future__ import print_function
import ntpath

import mimetypes
import os
import sys
import base64
from urllib3.fields import RequestField
from urllib3.filepost import encode_multipart_formdata

from twisted.internet import reactor, defer
from twisted.internet.endpoints import connectProtocol, SSL4ClientEndpoint
from twisted.internet.protocol import Protocol
from twisted.internet.ssl import optionsForClientTLS
from h2 import settings
from h2.connection import H2Connection
from h2.events import (
    ResponseReceived, DataReceived, StreamEnded, StreamReset, WindowUpdated,
    SettingsAcknowledged,PushedStreamReceived
)


AUTHORITY = u'localhost2'
PATH = '/'


class H2Protocol(Protocol):
    def __init__(self, file_path):
        self.conn = H2Connection()
        self.known_proto = None
        self.request_made = False
        self.request_complete = False
        self.file_path = file_path
        self.flow_control_deferred = None
        self.fileobj = None
        self.file_size = None

    def connectionMade(self):
        """
        Called by Twisted when the TCP connection is established. We can start
        sending some data now: we should open with the connection preamble.
        """
        self.conn.initiate_connection()
        self.transport.write(self.conn.data_to_send())

    def dataReceived(self, data):
        """
        Called by Twisted when data is received on the connection.

        We need to check a few things here. Firstly, we want to validate that
        we actually negotiated HTTP/2: if we didn't, we shouldn't proceed!

        Then, we want to pass the data to the protocol stack and check what
        events occurred.
        """
        if not self.known_proto:
            self.known_proto = self.transport.negotiatedProtocol
            assert self.known_proto == b'h2'

        events = self.conn.receive_data(data)
        print(events)

        for event in events:
            if isinstance(event, ResponseReceived):
                print(event)
                self.handleResponse(event.headers)
            elif isinstance(event, DataReceived):
                print(event)
                self.handleData(event.data)
            elif isinstance(event, PushedStreamReceived):
                self.handlePushedStreamReceived(event)
            elif isinstance(event, StreamEnded):
                print(event)
                self.endStream()
            elif isinstance(event, SettingsAcknowledged):
                print(event)
                self.settingsAcked(event)
            elif isinstance(event, StreamReset):
                print(event)
                reactor.stop()
                raise RuntimeError("Stream reset: %d" % event.error_code)

        data = self.conn.data_to_send()
        self.transport.write(data)

    def settingsAcked(self, event):
        """
        Called when the remote party ACKs our settings. We send a SETTINGS
        frame as part of the preamble, so if we want to be
        if data: very polite we can
        wait until the ACK for that frame comes before we start sending our
        request.
        """

        if not self.request_made:
            self.sendRequest()


    def handleResponse(self, response_headers):
        """
        Handle the response by printing the response headers.
        """
        for name, value in response_headers:
            # print("%s: %s" % (name.decode('utf-8'), value.decode('utf-8')))
            print("%s: %s" % (name, value))

        print("")

    def handleData(self, data):
        """
        We handle data that's received by just printing it.
        """
        print(data, end='')

    def endStream(self):
        """
        We call this when the stream is cleanly ended by the remote peer. That
        means that the response is complete.

        Because this code only makes a single HTTP/2 request, once we receive
        the complete response we can safely tear the connection down and stop
        the reactor. We do that as cleanly as possible.
        """
        self.request_complete = True
        self.conn.close_connection()
        self.transport.write(self.conn.data_to_send())
        self.transport.loseConnection()

    def handlePushedStreamReceived(self, event):
        # print(event.pushed_stream_id)
        # print(event.parent_stream_id)
        # print(event.headers)
        # self.conn.prioritize(1)
        self.count = 0
        if self.count == 0:
            response_headers = [
                # (':method', 'GET'),
                # (':authority', AUTHORITY),
                # (':scheme', 'https'),
                # (':path', '/data/images/99f2374e-92cd-4082-86de-2627924e364fIMG_79011165386531.jpeg'),
                # ('user-agent', 'hyper-h2/1.0.0')
            ]
            self.conn.send_headers(event.pushed_stream_id, event.headers)
            self.count += 1
        return

    def connectionLost(self, reason=None):
        """
        Called by Twisted when the connection is gone. Regardless of whether
        it was clean or not, we want to stop the reactor.
        """
        if self.fileobj is not None:
            self.fileobj = None

        if reactor.running:
            reactor.stop()

    def sendRequest(self):
        """
        Send the GET request.

        """

        # Now we can build a header block.
        request_headers = [
            (':method', 'GET'),
            (':authority', AUTHORITY),
            (':scheme', 'https'),
            (':path', PATH),
            ('user-agent', 'hyper-h2/1.0.0')
        ]

        
        self.conn.send_headers(1, request_headers)
        self.request_made = True


try:
    filename = sys.argv[1]
except IndexError:
    filename = __file__

options = optionsForClientTLS(
    hostname=AUTHORITY,
    acceptableProtocols=[b'h2'],
)

connectProtocol(
    SSL4ClientEndpoint(reactor, AUTHORITY, 443, options),
    H2Protocol(filename)
)
reactor.run()
