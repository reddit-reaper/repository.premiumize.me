"""
    Premiumize Kodi Addon
    Copyright (C) 2016 tknorris

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import urllib
import json
import local_lib.log_utils as log_utils
import local_lib.kodi as kodi
from urllib import parse
from urllib import request


def __enum(**enums):
    return type('Enum', (), enums)

BASE_URL = 'premiumize.me'
TIMEOUT = 30
BOUNDARY = 'X-X-X'
USER_AGENT = 'Premiumize Addon for Kodi/%s' % (kodi.get_version())
DOWN_TYPES = __enum(NZB='nzb', TORRENT='torrent')


class PremiumizeError(Exception):
    pass

class Premiumize_API():
    def __init__(self, customer_id, pin):
        self.customer_id = customer_id
        self.pin = pin
        scheme = 'https'
        prefix = 'www'
        self.base_url = '%s://%s.%s' % (scheme, prefix, BASE_URL)
    
    def create_folder(self, name, parent_id=None):
        url = '/api/folder/create'
        params = {'name': name}
        if parent_id is not None:
            params['parent_id'] = parent_id
        return self.__call_premiumize(url, params=params)
    
    def rename_folder(self, name, folder_id):
        url = '/api/folder/rename'
        params = {'id': folder_id, 'name': name}
        return self.__call_premiumize(url, params=params)
    
    def clear_finished(self):
        url = '/api/transfer/clearfinished'
        return self.__call_premiumize(url)
    
    def delete_transfer(self, torrent_id):
        url = '/api/transfer/delete'
        params = {'type': 'torrent', 'id': torrent_id}
        return self.__call_premiumize(url, params=params)
    
    def delete_item(self, torrent_id):
        url = '/api/item/delete'
        params = {'type': 'torrent', 'id': torrent_id}
        return self.__call_premiumize(url, params=params)
    
    def delete_folder(self, folder_id):
        url = '/api/folder/delete'
        params = {'id': folder_id}
        return self.__call_premiumize(url, params=params)
    
    def get_transfers(self):
        url = '/api/transfer/list'
        return self.__call_premiumize(url)
    
    def get_files(self, torrent_id=None):
        url = '/api/folder/list'
        if torrent_id is not None:
            params = {'id': torrent_id}
        else:
            params = None
        return self.__call_premiumize(url, params=params)
        
    def browse_torrent(self, hash_id):
        url = '/api/torrent/browse'
        params = {'hash': hash_id}
        return self.__call_premiumize(url, params=params)
    
    def add_download(self, download, download_type, folder_id=None, file_name=None):
        url = '/api/transfer/create'
        params = {'type': download_type}
        if folder_id is not None:
            params['folder_id'] = folder_id
        
        if download.startswith('http') or download.startswith('magnet'):
            data = {'src': download}
            return self.__call_premiumize(url, params=params, data=data)
        else:
            if file_name is None: file_name = 'dummy.' + download_type
            mime_type = 'application/x-nzb' if download_type == DOWN_TYPES.NZB else 'application/x-bittorrent'
            multipart_data = '--%s\n' % (BOUNDARY)
            multipart_data += 'Content-Disposition: form-data; name="src"; filename="%s"\n' % (file_name)
            multipart_data += 'Content-Type: %s\n\n' % (mime_type)
            multipart_data += download
            multipart_data += '\n--%s--\n' % (BOUNDARY)
            log_utils.log('Multipart Data: |%s|%s|' % (BOUNDARY, len(download)), log_utils.LOGDEBUG)
            return self.__call_premiumize(url, params=params, multipart_data=multipart_data)
    
    def __call_premiumize(self, url, params=None, data=None, multipart_data=None):
        if not self.customer_id or not self.pin:
            return {}

        headers = {'User-Agent': USER_AGENT}
        url = '%s%s' % (self.base_url, url)
        if params is None: params = {}
        params.update({'customer_id': self.customer_id, 'pin': self.pin})
        if params: url = url + '?' + parse.urlencode(params)
        if data is not None and not isinstance(data, str):
            data = parse.urlencode(data).encode("utf-8") if data else None
        
        if multipart_data is not None:
            headers['Content-Type'] = 'multipart/form-data; boundary=%s' % (BOUNDARY)
            data = multipart_data
            
        log_data = len(data) if data and len(data) > 255 else data
        log_utils.log('Premiumize Call: Url: |%s| Headers: |%s| Data: |%s|' % (url, headers, log_data), log_utils.LOGDEBUG)
        request = urllib.request.Request(url, data=data)
        for key in headers: request.add_header(key, headers[key])
        response = urllib.request.urlopen(request, timeout=TIMEOUT)
        result = ''
        while True:
            data = response.read().decode('utf-8')
            if not data: break
            result += data

        try:
            js_data = json.loads(result)
            if 'status' in js_data and js_data['status'] != 'success':
                msg = js_data.get('message', 'Unknown Error')
                log_utils.log('Premiumize Error Response: %s - %s' % (url, msg), log_utils.LOGERROR)
                raise PremiumizeError(msg)
        except ValueError:
            js_data = {}
            log_utils.log('Invalid JSON Premiumize API Response: %s - |%s|' % (url, js_data), log_utils.LOGERROR)

        # log_utils.log('Premiumize Response: %s' % (js_data), log_utils.LOGDEBUG)
        return js_data
