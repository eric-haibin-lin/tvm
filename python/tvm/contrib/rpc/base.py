"""Base definitions for RPC."""
from __future__ import absolute_import

import socket
import time
import json
import errno
import struct
import random
import logging

from ..._ffi.function import _init_api
from ..._ffi.base import py_str

# Magic header for RPC data plane
RPC_MAGIC = 0xff271
# magic header for RPC tracker(control plane)
RPC_TRACKER_MAGIC = 0x2f271
# sucess response
RPC_CODE_SUCCESS = RPC_MAGIC + 0
# duplicate key in proxy
RPC_CODE_DUPLICATE = RPC_MAGIC + 1
# cannot found matched key in server
RPC_CODE_MISMATCH = RPC_MAGIC + 2


class TrackerCode(object):
    """Enumeration code for the RPC tracker"""
    FAIL = -1
    SUCCESS = 0
    PING = 1
    STOP = 2
    PUT = 3
    REQUEST = 4
    UPDATE_INFO = 5
    SUMMARY = 6

RPC_SESS_MASK = 128


def recvall(sock, nbytes):
    """Receive all nbytes from socket.

    Parameters
    ----------
    sock: Socket
       The socket

    nbytes : int
       Number of bytes to be received.
    """
    res = []
    nread = 0
    while nread < nbytes:
        chunk = sock.recv(min(nbytes - nread, 1024))
        if not chunk:
            raise IOError("connection reset")
        nread += len(chunk)
        res.append(chunk)
    return b"".join(res)


def sendjson(sock, data):
    """send a python value to remote via json

    Parameters
    ----------
    sock : Socket
        The socket

    data : object
        Python value to be sent.
    """
    data = json.dumps(data)
    sock.sendall(struct.pack("@i", len(data)))
    sock.sendall(data.encode("utf-8"))


def recvjson(sock):
    """receive python value from remote via json

    Parameters
    ----------
    sock : Socket
        The socket

    Returns
    -------
    value : object
        The value received.
    """
    size = struct.unpack("@i", recvall(sock, 4))[0]
    data = json.loads(py_str(recvall(sock, size)))
    return data


def random_key(prefix, cmap=None):
    """Generate a random key

    Parameters
    ----------
    prefix : str
        The string prefix

    cmap : dict
        Conflict map

    Returns
    -------
    key : str
        The generated random key
    """
    if cmap:
        while True:
            key = prefix + str(random.random())
            if key not in cmap:
                return key
    else:
        return prefix + str(random.random())


def connect_with_retry(addr, timeout=60, retry_period=5):
    """Connect to a TPC address with retry

    This function is only reliable to short period of server restart.

    Parameters
    ----------
    addr : tuple
        address tuple

    timeout : float
         Timeout during retry

    retry_period : float
         Number of seconds before we retry again.
    """
    tstart = time.time()
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(addr)
            return sock
        except socket.error as sock_err:
            if sock_err.args[0] not in (errno.ECONNREFUSED,):
                raise sock_err
            period = time.time() - tstart
            if period > timeout:
                raise RuntimeError(
                    "Failed to connect to server %s" % str(addr))
            logging.info("Cannot connect to tracker%s, retry in %g secs...",
                         str(addr), retry_period)
            time.sleep(retry_period)


# Still use tvm.contrib.rpc for the foreign functions
_init_api("tvm.contrib.rpc", "tvm.contrib.rpc.base")
