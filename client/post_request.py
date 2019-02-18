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
    SettingsAcknowledged,
)


AUTHORITY = u'localhost2'
PATH = '/upload'


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
            elif isinstance(event, WindowUpdated):
                print(event)
                self.windowUpdated(event)

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

        print(self.flow_control_deferred)
        if self.flow_control_deferred is None:
            if not self.request_made:
                self.sendRequest()
            return

        # Make sure we remove the flow control deferred to avoid firing it
        # more than once.
        flow_control_deferred = self.flow_control_deferred
        self.flow_control_deferred = None
        flow_control_deferred.callback(1)


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

    def windowUpdated(self, event):
        """
        We call this when the flow control window for the connection or the
        stream has been widened. If there's a flow control deferred present
        (that is, if we're blocked behind the flow control), we fire it.
        Otherwise, we do nothing.
        """
        print(self.conn.local_flow_control_window(stream_id=1))
        if self.flow_control_deferred is None:
            return

        # Make sure we remove the flow control deferred to avoid firing it
        # more than once.
        flow_control_deferred = self.flow_control_deferred
        self.flow_control_deferred = None
        flow_control_deferred.callback(1)

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
        Send the POST request.

        A POST request is made up of one headers frame, and then 0+ data
        frames. This method begins by sending the headers, and then starts a
        series of calls to send data.
        """
        # First, we need to work out how large the file is.
        self.file_size = os.stat(self.file_path).st_size

        # We can now open the file.
        file = open(self.file_path, "rb")
        try:
            self.fileobj = file.read()
        finally:
            file.close()

        # Next, we want to guess a content-type and content-encoding.
        content_type, content_encoding = mimetypes.guess_type(self.file_path)
        rf = RequestField(name='file', data=self.fileobj, filename=ntpath.basename(self.file_path))
        print(rf)
        print(content_type)
        rf.make_multipart(content_type=content_type)
        print(rf.data)
        body, content_type = encode_multipart_formdata([rf])
        self.fileobj = body

        # Now we can build a header block.
        request_headers = [
            (':method', 'POST'),
            (':authority', AUTHORITY),
            (':scheme', 'https'),
            (':path', PATH),
            ('user-agent', 'hyper-h2/1.0.0'),
            ('content-length', str(self.file_size)),
        ]

        if content_type is not None:
            request_headers.append(('content-type', content_type))

            if content_encoding is not None:
                request_headers.append(('content-encoding', content_encoding))

        
        self.conn.send_headers(1, request_headers)
        self.request_made = True

        # We now need to send all the relevant data. We do this by checking
        # what the acceptable amount of data is to send, and sending it. If we
        # find ourselves blocked behind flow control, we then place a deferred
        # and wait until that deferred fires.
        self.sendFileData(stream_id=1)

    def sendFileData(self, stream_id=1):
            
        """
        Send some file data on the connection.
        """
        # Firstly, check what the flow control window is for stream 1.
        window_size = self.conn.local_flow_control_window(stream_id=stream_id)
        print("Window_size: %d \n" % window_size)

        # Next, check what the maximum frame size is.
        max_frame_size = self.conn.max_outbound_frame_size

        # We will send no more than the window size or the remaining file size
        # of data in this call, whichever is smaller.
        bytes_to_send = min(window_size, self.file_size)

        # We now need to send a number of data frames.
        while bytes_to_send > 0:
            chunk_size = min(bytes_to_send, max_frame_size)
            print(chunk_size)
            print("\n")
            print(bytes_to_send)
            print("\n")
            # data_chunk = self.fileobj.read(chunk_size)
            data_chunk = self.fileobj[:chunk_size]
            self.fileobj = self.fileobj[chunk_size:len(self.fileobj)]
            # print(base64.b64encode(data_chunk).len())
            print("Done chunking data!")
            self.conn.send_data(stream_id=stream_id, data=data_chunk)
            print("Done sending data!")

            bytes_to_send -= chunk_size
            self.file_size -= chunk_size
            if self.file_size < 0:
                self.file_size = 0
        
        print("\n")
        print("Remaining File Size: ")
        print(self.file_size)

        # We've prepared a whole chunk of data to send. If the file is fully
        # sent, we also want to end the stream: we're done here.
        if self.file_size == 0:
            self.conn.end_stream(stream_id=stream_id)
        else:
            # We've still got data left to send but the window is closed. Save
            # a Deferred that will call us when the window gets opened.
            self.flow_control_deferred = defer.Deferred()
            self.flow_control_deferred.addCallback(self.sendFileData)
            # self.conn.increment_flow_control_window(increment=298588, stream_id=1)
            # self.conn.update_settings(
            #     {settings.SettingCodes.INITIAL_WINDOW_SIZE: 298588}
            # )
            # self.conn.send_headers

        self.transport.write(self.conn.data_to_send())


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
