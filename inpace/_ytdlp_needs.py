"""Parts of Python that yt-dlp (offline YouTube lessons) uses.

inPace fetches yt-dlp after it is installed (see offline.py), but the installers for Windows, macOS and Linux
only pack the parts of Python that inPace itself imports. Listing them here makes the installer builder
(PyInstaller) pack them too. This is never called."""


def _for_the_installer() -> None:  # pragma: no cover
    try:
        import abc  # noqa: F401
    except ImportError:
        pass
    try:
        import asyncio  # noqa: F401
    except ImportError:
        pass
    try:
        import atexit  # noqa: F401
    except ImportError:
        pass
    try:
        import base64  # noqa: F401
    except ImportError:
        pass
    try:
        import binascii  # noqa: F401
    except ImportError:
        pass
    try:
        import bisect  # noqa: F401
    except ImportError:
        pass
    try:
        import bz2  # noqa: F401
    except ImportError:
        pass
    try:
        import calendar  # noqa: F401
    except ImportError:
        pass
    try:
        import codecs  # noqa: F401
    except ImportError:
        pass
    try:
        import collections  # noqa: F401
    except ImportError:
        pass
    try:
        import collections.abc  # noqa: F401
    except ImportError:
        pass
    try:
        import concurrent.futures  # noqa: F401
    except ImportError:
        pass
    try:
        import contextlib  # noqa: F401
    except ImportError:
        pass
    try:
        import contextvars  # noqa: F401
    except ImportError:
        pass
    try:
        import copy  # noqa: F401
    except ImportError:
        pass
    try:
        import ctypes  # noqa: F401
    except ImportError:
        pass
    try:
        import ctypes.wintypes  # noqa: F401
    except ImportError:
        pass
    try:
        import dataclasses  # noqa: F401
    except ImportError:
        pass
    try:
        import datetime  # noqa: F401
    except ImportError:
        pass
    try:
        import email.header  # noqa: F401
    except ImportError:
        pass
    try:
        import email.message  # noqa: F401
    except ImportError:
        pass
    try:
        import email.parser  # noqa: F401
    except ImportError:
        pass
    try:
        import email.policy  # noqa: F401
    except ImportError:
        pass
    try:
        import email.utils  # noqa: F401
    except ImportError:
        pass
    try:
        import encodings.idna  # noqa: F401
    except ImportError:
        pass
    try:
        import enum  # noqa: F401
    except ImportError:
        pass
    try:
        import errno  # noqa: F401
    except ImportError:
        pass
    try:
        import fileinput  # noqa: F401
    except ImportError:
        pass
    try:
        import functools  # noqa: F401
    except ImportError:
        pass
    try:
        import getpass  # noqa: F401
    except ImportError:
        pass
    try:
        import glob  # noqa: F401
    except ImportError:
        pass
    try:
        import gzip  # noqa: F401
    except ImportError:
        pass
    try:
        import hashlib  # noqa: F401
    except ImportError:
        pass
    try:
        import heapq  # noqa: F401
    except ImportError:
        pass
    try:
        import hmac  # noqa: F401
    except ImportError:
        pass
    try:
        import html.entities  # noqa: F401
    except ImportError:
        pass
    try:
        import html.parser  # noqa: F401
    except ImportError:
        pass
    try:
        import http  # noqa: F401
    except ImportError:
        pass
    try:
        import http.client  # noqa: F401
    except ImportError:
        pass
    try:
        import http.cookiejar  # noqa: F401
    except ImportError:
        pass
    try:
        import http.cookies  # noqa: F401
    except ImportError:
        pass
    try:
        import http.server  # noqa: F401
    except ImportError:
        pass
    try:
        import importlib  # noqa: F401
    except ImportError:
        pass
    try:
        import importlib.abc  # noqa: F401
    except ImportError:
        pass
    try:
        import importlib.machinery  # noqa: F401
    except ImportError:
        pass
    try:
        import importlib.resources  # noqa: F401
    except ImportError:
        pass
    try:
        import importlib.util  # noqa: F401
    except ImportError:
        pass
    try:
        import inspect  # noqa: F401
    except ImportError:
        pass
    try:
        import io  # noqa: F401
    except ImportError:
        pass
    try:
        import itertools  # noqa: F401
    except ImportError:
        pass
    try:
        import json  # noqa: F401
    except ImportError:
        pass
    try:
        import locale  # noqa: F401
    except ImportError:
        pass
    try:
        import logging  # noqa: F401
    except ImportError:
        pass
    try:
        import lzma  # noqa: F401
    except ImportError:
        pass
    try:
        import math  # noqa: F401
    except ImportError:
        pass
    try:
        import mimetypes  # noqa: F401
    except ImportError:
        pass
    try:
        import netrc  # noqa: F401
    except ImportError:
        pass
    try:
        import operator  # noqa: F401
    except ImportError:
        pass
    try:
        import optparse  # noqa: F401
    except ImportError:
        pass
    try:
        import os  # noqa: F401
    except ImportError:
        pass
    try:
        import os.path  # noqa: F401
    except ImportError:
        pass
    try:
        import pathlib  # noqa: F401
    except ImportError:
        pass
    try:
        import pkgutil  # noqa: F401
    except ImportError:
        pass
    try:
        import platform  # noqa: F401
    except ImportError:
        pass
    try:
        import quopri  # noqa: F401
    except ImportError:
        pass
    try:
        import random  # noqa: F401
    except ImportError:
        pass
    try:
        import re  # noqa: F401
    except ImportError:
        pass
    try:
        import secrets  # noqa: F401
    except ImportError:
        pass
    try:
        import shlex  # noqa: F401
    except ImportError:
        pass
    try:
        import shutil  # noqa: F401
    except ImportError:
        pass
    try:
        import signal  # noqa: F401
    except ImportError:
        pass
    try:
        import socket  # noqa: F401
    except ImportError:
        pass
    try:
        import sqlite3  # noqa: F401
    except ImportError:
        pass
    try:
        import ssl  # noqa: F401
    except ImportError:
        pass
    try:
        import string  # noqa: F401
    except ImportError:
        pass
    try:
        import struct  # noqa: F401
    except ImportError:
        pass
    try:
        import subprocess  # noqa: F401
    except ImportError:
        pass
    try:
        import sys  # noqa: F401
    except ImportError:
        pass
    try:
        import sysconfig  # noqa: F401
    except ImportError:
        pass
    try:
        import tempfile  # noqa: F401
    except ImportError:
        pass
    try:
        import textwrap  # noqa: F401
    except ImportError:
        pass
    try:
        import threading  # noqa: F401
    except ImportError:
        pass
    try:
        import time  # noqa: F401
    except ImportError:
        pass
    try:
        import tokenize  # noqa: F401
    except ImportError:
        pass
    try:
        import traceback  # noqa: F401
    except ImportError:
        pass
    try:
        import types  # noqa: F401
    except ImportError:
        pass
    try:
        import typing  # noqa: F401
    except ImportError:
        pass
    try:
        import unicodedata  # noqa: F401
    except ImportError:
        pass
    try:
        import urllib  # noqa: F401
    except ImportError:
        pass
    try:
        import urllib.error  # noqa: F401
    except ImportError:
        pass
    try:
        import urllib.parse  # noqa: F401
    except ImportError:
        pass
    try:
        import urllib.request  # noqa: F401
    except ImportError:
        pass
    try:
        import urllib.response  # noqa: F401
    except ImportError:
        pass
    try:
        import uuid  # noqa: F401
    except ImportError:
        pass
    try:
        import warnings  # noqa: F401
    except ImportError:
        pass
    try:
        import xml.dom.minidom  # noqa: F401
    except ImportError:
        pass
    try:
        import xml.etree.ElementTree  # noqa: F401
    except ImportError:
        pass
    try:
        import zipfile  # noqa: F401
    except ImportError:
        pass
    try:
        import zipimport  # noqa: F401
    except ImportError:
        pass
    try:
        import zlib  # noqa: F401
    except ImportError:
        pass
