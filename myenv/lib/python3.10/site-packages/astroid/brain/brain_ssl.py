# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/PyCQA/astroid/blob/main/CONTRIBUTORS.txt

"""Astroid hooks for the ssl library."""

from astroid import parse
from astroid.brain.helpers import register_module_extender
from astroid.const import PY38_PLUS, PY310_PLUS
from astroid.manager import AstroidManager


def _verifyflags_enum() -> str:
    enum = """
    class VerifyFlags(_IntFlag):
        VERIFY_DEFAULT = 0
        VERIFY_CRL_CHECK_LEAF = 1
        VERIFY_CRL_CHECK_CHAIN = 2
        VERIFY_X509_STRICT = 3
        VERIFY_X509_TRUSTED_FIRST = 4"""
    if PY310_PLUS:
        enum += """
        VERIFY_ALLOW_PROXY_CERTS = 5
        VERIFY_X509_PARTIAL_CHAIN = 6
        """
    return enum


def _options_enum() -> str:
    enum = """
    class Options(_IntFlag):
        OP_ALL = 1
        OP_NO_SSLv2 = 2
        OP_NO_SSLv3 = 3
        OP_NO_TLSv1 = 4
        OP_NO_TLSv1_1 = 5
        OP_NO_TLSv1_2 = 6
        OP_NO_TLSv1_3 = 7
        OP_CIPHER_SERVER_PREFERENCE = 8
        OP_SINGLE_DH_USE = 9
        OP_SINGLE_ECDH_USE = 10
        OP_NO_COMPRESSION = 11
        OP_NO_TICKET = 12
        OP_NO_RENEGOTIATION = 13"""
    if PY38_PLUS:
        enum += """
        OP_ENABLE_MIDDLEBOX_COMPAT = 14"""
    return enum


def ssl_transform():
    return parse(
        """
    # Import necessary for conversion of objects defined in C into enums
    from enum import IntEnum as _IntEnum, IntFlag as _IntFlag

    from _ssl import OPENSSL_VERSION_NUMBER, OPENSSL_VERSION_INFO, OPENSSL_VERSION
    from _ssl import _SSLContext, MemoryBIO
    from _ssl import (
        SSLError, SSLZeroReturnError, SSLWantReadError, SSLWantWriteError,
        SSLSyscallError, SSLEOFError,
        )
    from _ssl import CERT_NONE, CERT_OPTIONAL, CERT_REQUIRED
    from _ssl import txt2obj as _txt2obj, nid2obj as _nid2obj
    from _ssl import RAND_status, RAND_add, RAND_bytes, RAND_pseudo_bytes
    try:
        from _ssl import RAND_egd
    except ImportError:
        # LibreSSL does not provide RAND_egd
        pass
    from _ssl import (OP_ALL, OP_CIPHER_SERVER_PREFERENCE,
                      OP_NO_COMPRESSION, OP_NO_SSLv2, OP_NO_SSLv3,
                      OP_NO_TLSv1, OP_NO_TLSv1_1, OP_NO_TLSv1_2,
                      OP_SINGLE_DH_USE, OP_SINGLE_ECDH_USE)

    from _ssl import (ALERT_DESCRIPTION_ACCESS_DENIED, ALERT_DESCRIPTION_BAD_CERTIFICATE,
                      ALERT_DESCRIPTION_BAD_CERTIFICATE_HASH_VALUE,
                      ALERT_DESCRIPTION_BAD_CERTIFICATE_STATUS_RESPONSE,
                      ALERT_DESCRIPTION_BAD_RECORD_MAC,
                      ALERT_DESCRIPTION_CERTIFICATE_EXPIRED,
                      ALERT_DESCRIPTION_CERTIFICATE_REVOKED,
                      ALERT_DESCRIPTION_CERTIFICATE_UNKNOWN,
                      ALERT_DESCRIPTION_CERTIFICATE_UNOBTAINABLE,
                      ALERT_DESCRIPTION_CLOSE_NOTIFY, ALERT_DESCRIPTION_DECODE_ERROR,
                      ALERT_DESCRIPTION_DECOMPRESSION_FAILURE,
                      ALERT_DESCRIPTION_DECRYPT_ERROR,
                      ALERT_DESCRIPTION_HANDSHAKE_FAILURE,
                      ALERT_DESCRIPTION_ILLEGAL_PARAMETER,
                      ALERT_DESCRIPTION_INSUFFICIENT_SECURITY,
                      ALERT_DESCRIPTION_INTERNAL_ERROR,
                      ALERT_DESCRIPTION_NO_RENEGOTIATION,
                      ALERT_DESCRIPTION_PROTOCOL_VERSION,
                      ALERT_DESCRIPTION_RECORD_OVERFLOW,
                      ALERT_DESCRIPTION_UNEXPECTED_MESSAGE,
                      ALERT_DESCRIPTION_UNKNOWN_CA,
                      ALERT_DESCRIPTION_UNKNOWN_PSK_IDENTITY,
                      ALERT_DESCRIPTION_UNRECOGNIZED_NAME,
                      ALERT_DESCRIPTION_UNSUPPORTED_CERTIFICATE,
                      ALERT_DESCRIPTION_UNSUPPORTED_EXTENSION,
                      ALERT_DESCRIPTION_USER_CANCELLED)
    from _ssl import (SSL_ERROR_EOF, SSL_ERROR_INVALID_ERROR_CODE, SSL_ERROR_SSL,
                      SSL_ERROR_SYSCALL, SSL_ERROR_WANT_CONNECT, SSL_ERROR_WANT_READ,
                      SSL_ERROR_WANT_WRITE, SSL_ERROR_WANT_X509_LOOKUP, SSL_ERROR_ZERO_RETURN)
    from _ssl import VERIFY_CRL_CHECK_CHAIN, VERIFY_CRL_CHECK_LEAF, VERIFY_DEFAULT, VERIFY_X509_STRICT
    from _ssl import HAS_SNI, HAS_ECDH, HAS_NPN, HAS_ALPN
    from _ssl import _OPENSSL_API_VERSION
    from _ssl import PROTOCOL_SSLv23, PROTOCOL_TLSv1, PROTOCOL_TLSv1_1, PROTOCOL_TLSv1_2
    from _ssl import PROTOCOL_TLS, PROTOCOL_TLS_CLIENT, PROTOCOL_TLS_SERVER

    class AlertDescription(_IntEnum):
        ALERT_DESCRIPTION_ACCESS_DENIED = 0
        ALERT_DESCRIPTION_BAD_CERTIFICATE = 1
        ALERT_DESCRIPTION_BAD_CERTIFICATE_HASH_VALUE = 2
        ALERT_DESCRIPTION_BAD_CERTIFICATE_STATUS_RESPONSE = 3
        ALERT_DESCRIPTION_BAD_RECORD_MAC = 4
        ALERT_DESCRIPTION_CERTIFICATE_EXPIRED = 5
        ALERT_DESCRIPTION_CERTIFICATE_REVOKED = 6
        ALERT_DESCRIPTION_CERTIFICATE_UNKNOWN = 7
        ALERT_DESCRIPTION_CERTIFICATE_UNOBTAINABLE = 8
        ALERT_DESCRIPTION_CLOSE_NOTIFY = 9
        ALERT_DESCRIPTION_DECODE_ERROR = 10
        ALERT_DESCRIPTION_DECOMPRESSION_FAILURE = 11
        ALERT_DESCRIPTION_DECRYPT_ERROR = 12
        ALERT_DESCRIPTION_HANDSHAKE_FAILURE = 13
        ALERT_DESCRIPTION_ILLEGAL_PARAMETER = 14
        ALERT_DESCRIPTION_INSUFFICIENT_SECURITY = 15
        ALERT_DESCRIPTION_INTERNAL_ERROR = 16
        ALERT_DESCRIPTION_NO_RENEGOTIATION = 17
        ALERT_DESCRIPTION_PROTOCOL_VERSION = 18
        ALERT_DESCRIPTION_RECORD_OVERFLOW = 19
        ALERT_DESCRIPTION_UNEXPECTED_MESSAGE = 20
        ALERT_DESCRIPTION_UNKNOWN_CA = 21
        ALERT_DESCRIPTION_UNKNOWN_PSK_IDENTITY = 22
        ALERT_DESCRIPTION_UNRECOGNIZED_NAME = 23
        ALERT_DESCRIPTION_UNSUPPORTED_CERTIFICATE = 24
        ALERT_DESCRIPTION_UNSUPPORTED_EXTENSION = 25
        ALERT_DESCRIPTION_USER_CANCELLED = 26

    class SSLErrorNumber(_IntEnum):
        SSL_ERROR_EOF = 0
        SSL_ERROR_INVALID_ERROR_CODE = 1
        SSL_ERROR_SSL = 2
        SSL_ERROR_SYSCALL = 3
        SSL_ERROR_WANT_CONNECT = 4
        SSL_ERROR_WANT_READ = 5
        SSL_ERROR_WANT_WRITE = 6
        SSL_ERROR_WANT_X509_LOOKUP = 7
        SSL_ERROR_ZERO_RETURN = 8

    class VerifyMode(_IntEnum):
        CERT_NONE = 0
        CERT_OPTIONAL = 1
        CERT_REQUIRED = 2
    """
        + _verifyflags_enum()
        + _options_enum()
    )


register_module_extender(AstroidManager(), "ssl", ssl_transform)
