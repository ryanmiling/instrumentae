#!/usr/bin/env python2
# -*- coding: utf-8 -*-

""" This module interfaces with the gdata Google API library
      to make functional API calls in accordance to their spec.
      While this library was specifically built in a Django app,
      Django is not required.
"""

from abc import ABCMeta, abstractmethod
from configparse import decrypt_token

import datetime
import gdata.gauth
import gdata.client
import gdata.spreadsheets.client
import functools
import json
import os
import requests
import time

import settings

TOKENS_FILE = os.path.join(os.path.dirname(__file__),"gauth_tokens.json")

class GClient(object):
    """ This class also handles maintaining a connection
          through token expirations.

        How OAuth2 works with Google:
          https://developers.google.com/identity/protocols/OAuth2

        How to refresh an access token:
          https://developers.google.com/identity/protocols/OAuth2ForDevices#refreshtoken
    """
    __metaclass__ = ABCMeta

    REFRESH_TOKEN_URL = 'https://www.googleapis.com/oauth2/v3/token'

    def __init__(self):
        """ Creates an object of the type GClient"""

        if self.NAME is None or self.SCOPE is None:
            raise Exception('GClient class cannot be instantiated alone. ' +
                            'Instantiate a subclass for a specific API.')

        self._client_id = decrypt_token(settings.GCLIENT_ID)
        self._client_secret = decrypt_token(settings.GCLIENT_SECRET)

        self._access_token = None
        self._expiry_from_epoch = None # datetime of token expiration

        tokens_json = self.load_tokens_file()
        if tokens_json:
            self._load_json_tokens(tokens_json)

    def load_tokens_file(self):
        """ Returns a dict of the parsed tokens file's content """

        tokens_json = {}
        if os.path.exists(TOKENS_FILE):
            retries = 5
            is_read = False
            while retries > 0:
                try:
                    with open(TOKENS_FILE, 'r') as tokens_file:
                        tokens_json = json.load(tokens_file)

                    is_read = True
                    break
                # another process is messing with the file
                except IOError:
                    time.sleep(5)
                finally:
                    retries -= 1

            if not is_read:
                raise Exception('Tokens file (%s) could not be read. Max retries reached.' % TOKENS_FILE)

        return tokens_json

    def _load_json_tokens(self, tokens_dict):
        """ Loads the tokens file's fields into this GClient

        Args:
          tokens_dict: dict of access tokens and expiry dates, keyed by names
                         of the Google APIs
        """

        if self.NAME in tokens_dict:
            api_tokens_dict = tokens_dict[self.NAME]
            # optional fields that may be in the file
            if 'access_token' in api_tokens_dict:
                self._access_token = api_tokens_dict['access_token']

            if 'expiry_from_epoch' in api_tokens_dict:
                expiry_from_epoch = api_tokens_dict['expiry_from_epoch']
                self._expiry_from_epoch = datetime.datetime.fromtimestamp(expiry_from_epoch)

    def save_tokens_file(self):
        """ Saves the tokens file (optionally) with the necessary fields for
              future oauths. Each Google API's tokens are saved so we can
              track multiple tokens & expiry dates.
        """

        tokens_json = self.load_tokens_file()
        if self.NAME not in tokens_json:
            tokens_json[self.NAME] = {}

        update_file = False

        # prevent unnecessary future refreshes if access-token is not expired
        if self._access_token is not None:
            tokens_json[self.NAME]['access_token'] = self._access_token
            update_file = True

        if self._expiry_from_epoch is not None:
            tokens_json[self.NAME]['expiry_from_epoch'] = int(self._expiry_from_epoch.strftime('%s'))
            update_file = True

        if update_file:
            retries = 5
            is_updated = False
            while retries > 0:
                try:
                    with open(TOKENS_FILE, 'w') as tokens_file:
                        json.dump(tokens_json, tokens_file)
                    is_updated = True
                    break
                except IOError:
                    time.sleep(5)
                finally:
                    retries -= 1

            if not is_updated:
                raise Exception('Tokens file (%s) could not be written. Max retries reached.' % TOKENS_FILE)

    def do_refresh_token(self):
        """ Return whether or not we should refresh our access token """

        return self._expiry_from_epoch is None or \
                self._expiry_from_epoch <= datetime.datetime.now()

    def refresh_token(self):
        """ Refresh our access-token because it has expired or we don't have one """

        payload = dict(client_id=self._client_id,
                       client_secret=self._client_secret,
                       refresh_token=self._refresh_token,
                       grant_type='refresh_token')

        res = requests.post(self.REFRESH_TOKEN_URL,
                            data=payload)

        if res.status_code != 200:
            raise Exception('Access token could not be refreshed\n%s' % res.text)

        json_res = json.loads(res.text)
        self._access_token = json_res['access_token']
        self._expiry_from_epoch = datetime.datetime.now() + \
                                    datetime.timedelta(seconds=json_res['expires_in'])

        self.save_tokens_file()

    @abstractmethod
    def poll(self, *args, **kwargs):
        """ Polls the Google API specifically the way it likes it """
        pass


class GDriveClient(GClient):
    """ Handles API calls to the Google Drive API """
    NAME = 'gdrive'
    SCOPE = 'https://www.googleapis.com/auth/drive'

    def __init__(self, *args, **kwargs):
        super(GDriveClient, self).__init__(*args, **kwargs)
        self._refresh_token = decrypt_token(settings.GDRIVE_REFRESH_TOKEN)

    def __build_request_headers(self, data=None):
        """ Builds the headers we'll include in a request to Google's API

        Args:
          data: str (optional) of JSON data we're passing into a request
        """
        headers = {}
        headers['Authorization'] = 'Bearer ' + str(self._access_token)
        headers['Content-Type'] = 'application/json'

        if data is not None:
            headers['Content-Length'] = len(str(data))

        return headers

    def poll(self, method_name, *args, **kwargs):
        """ Polls the GDrive API, RESTfully with HTTP and the right headers,
              and always returns a dictionary of values (from JSON).

        Args:
          method_name: string representing the HTTP method we want to send to the
                         API (one of get, post, put)
          args: list (optional) of args for the method to be called
          kwargs: dict (optional) of keyword-args for the method to be called
        """

        if method_name not in {'get', 'post', 'put'}:
            raise ValueError('Drive API does not support the %s HTTP method. ' +
                             'Must be one of get, post, or put.' % method_name)

        headers = {}
        if 'data' in kwargs:
            # cast to a string b/c the content-type is json
            kwargs['data'] = str(kwargs['data'])
            headers = self.__build_request_headers(kwargs['data'])
        else:
            headers = self.__build_request_headers()

        kwargs['headers'] = headers

        api_call = functools.partial(getattr(requests, method_name), *args, **kwargs)

        res = None
        retries = 5
        while retries > 0:
            try:
                res = api_call()
                if res.status_code == 200:
                    break
                elif res.status_code == 401:
                    self.refresh_token()

                    # we have to rebuild the headers so they have the new token
                    kwargs['headers'] = self.__build_request_headers(kwargs.get('data'))
                    api_call = functools.partial(getattr(requests, method_name), *args, **kwargs)

                    retries = 2 # only retry once more after we refresh the token
            except Exception: # API may have blipped
                time.sleep(5)
            finally:
                retries -= 1

        if res is None:
            raise Exception('Unable to get a response from the API')

        return res.json()


class GSheetClient(GClient):
    """ Represents a Google Spreadsheet client, connecting to the
          Google Spreadsheets API through OAuth2.
    """

    NAME = 'gsheet'
    SCOPE = 'https://spreadsheets.google.com/feeds'

    def __init__(self, *args, **kwargs):
        super(GSheetClient, self).__init__(*args, **kwargs)
        self.__client = None
        self._refresh_token = decrypt_token(settings.GSHEETS_REFRESH_TOKEN)

    @property
    def client(self):
        """ Handles creating or recreating the GClient if the token needs to be
              refreshed or has never been created
        """
        if self.do_refresh_token():
            self.refresh_token()
        elif self.__client is not None: # refresh is good, we've already pre-populated
            return self.__client

        auth_token = gdata.gauth.OAuth2Token(self._client_id,
                                             self._client_secret,
                                             scope=self.SCOPE,
                                             access_token=self._access_token,
                                             refresh_token=self._refresh_token,
                                             user_agent='InsightSquared')

        self.__client = gdata.spreadsheets.client.SpreadsheetsClient(auth_token=auth_token)
        return self.__client

    def poll(self, method_name, *args, **kwargs):
        """ Polls the Google Spreadsheets API client using the gdata lib with
              the provided args at the last minute possible.

        Args:
          method_name: string of the method to be called for the Google API client
          args: list (optional) of args for the API method to be called
          kwargs: dict (optional) of keyword-args for the API method to be called
        """

        if not hasattr(self.client, method_name):
            raise ValueError('Client of this scope does not own the method %s' % method_name)

        api_call = functools.partial(getattr(self.client, method_name), *args, **kwargs)

        res = None
        retries = 5
        while retries > 0:
            try:
                res = api_call()
                break
            # 401, refresh the token, it didn't get refreshed in client() prob from a
            #   wrong expiry or we're close to the expiration date
            except gdata.client.Unauthorized:
                self.refresh_token()
            except Exception: # API may have blipped
                time.sleep(5)
            finally:
                retries -= 1

        if res is None:
            raise Exception('Unable to get a response from the API')

        return res
