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
import re
import kodi
import urllib2
import urllib
import urlparse
import os.path
import log_utils
import xbmc
import xbmcvfs
from kodi import i18n

def __enum(**enums):
    return type('Enum', (), enums)

CHUNK_SIZE = 512 * 1024
DEFAULT_EXT = '.zip'
PROGRESS = __enum(OFF=0, WINDOW=1, BACKGROUND=2)

def format_size(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Y', suffix)

def make_info(name):
    info = {}
    sxe_patterns = [
        '(.*?)[._ -]s([0-9]+)[._ -]*e([0-9]+)',
        '(.*?)[._ -]([0-9]+)x([0-9]+)',
        # '(.*?)[._ -]([0-9]+)([0-9][0-9])', removed due to looking like Movie.Title.YYYY
        '(.*?)[._ -]?season[._ -]*([0-9]+)[._ -]*-?[._ -]*episode[._ -]*([0-9]+)',
        '(.*?)[._ -]\[s([0-9]+)\][._ -]*\[e([0-9]+)\]',
        '(.*?)[._ -]s([0-9]+)[._ -]*ep([0-9]+)']
    
    show_title = ''
    season = ''
    episode = ''
    airdate = ''
    for pattern in sxe_patterns:
        match = re.search(pattern, name, re.I)
        if match:
            show_title, season, episode = match.groups()
            break
    else:
        airdate_pattern = '(.*?)[. _](\d{4})[. _](\d{2})[. _](\d{2})[. _]'
        match = re.search(airdate_pattern, name)
        if match:
            show_title, year, month, day = match.groups()
            airdate = '%s-%s-%s' % (year, month, day)
    
    if show_title:
        show_title = re.sub('[._ -]', ' ', show_title)
        show_title = re.sub('\s\s+', ' ', show_title)
        info['title'] = name
        info['tvshowtitle'] = show_title
        if season: info['season'] = str(int(season))
        if episode: info['episode'] = str(int(episode))
        if airdate: info['aired'] = info['premiered'] = airdate
    else:
        pattern = '(.*?)[._ -](\d{4})[._ -](.*?)'
        match = re.search(pattern, name)
        if match:
            title, year, _extra = match.groups()
            title = re.sub('[._ -]', ' ', title)
            title = re.sub('\s\s+', ' ', title)
            info['title'] = title
            info['year'] = year
        
    return info

def format_time(seconds):
    minutes, seconds = divmod(seconds, 60)
    if minutes > 60:
        hours, minutes = divmod(minutes, 60)
        return "%02dh:%02dm:%02ds" % (hours, minutes, seconds)
    else:
        return "%02dm:%02ds" % (minutes, seconds)

def make_excl_list():
    excl_str = kodi.get_setting('video_filter')
    excl_list = excl_str.split(',')
    excl_list = [item.upper().strip() for item in excl_list]
    return excl_list

def download_media(url, path, file_name):
    try:
        progress = int(kodi.get_setting('down_progress'))
        active = not progress == PROGRESS.OFF
        background = progress == PROGRESS.BACKGROUND
        with kodi.ProgressDialog('Premiumize Cloud', i18n('downloading') % (file_name), background=background, active=active) as pd:
            request = urllib2.Request(url, headers={'User-Agent' : "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.2 (KHTML, like Gecko) Chrome/22.0.1216.0 Safari/537.2"})
            response = urllib2.urlopen(request)
            content_length = 0
            if 'Content-Length' in response.info():
                content_length = int(response.info()['Content-Length'])
    
            full_path = os.path.join(path, file_name)
            log_utils.log('Downloading: %s -> %s' % (url, full_path), log_utils.LOGDEBUG)
    
            path = xbmc.makeLegalFilename(path)
            if not xbmcvfs.exists(path):
                try:
                    try: xbmcvfs.mkdirs(path)
                    except: os.mkdir(path)
                except Exception as e:
                    raise Exception(i18n('failed_create_dir'))
    
            file_desc = xbmcvfs.File(full_path, 'w')
            total_len = 0
            cancel = False
            while True:
                data = response.read(CHUNK_SIZE)
                if not data:
                    break
    
                if pd.is_canceled():
                    cancel = True
                    break
    
                total_len += len(data)
                if not file_desc.write(data):
                    raise Exception(i18n('failed_write_file'))
    
                percent_progress = (total_len) * 100 / content_length if content_length > 0 else 0
                log_utils.log('Position : %s / %s = %s%%' % (total_len, content_length, percent_progress), log_utils.LOGDEBUG)
                pd.update(percent_progress)
            
            file_desc.close()

        if not cancel:
            kodi.notify(msg=i18n('download_complete') % (file_name), duration=5000)
            log_utils.log('Download Complete: %s -> %s' % (url, full_path), log_utils.LOGDEBUG)

    except Exception as e:
        log_utils.log('Error (%s) during download: %s -> %s' % (str(e), url, file_name), log_utils.LOGERROR)
        kodi.notify(msg=i18n('download_error') % (str(e), file_name), duration=5000)

def get_extension(url, response):
    filename = url2name(url)
    if 'Content-Disposition' in response.info():
        cd_list = response.info()['Content-Disposition'].split('filename=')
        if len(cd_list) > 1:
            filename = cd_list[-1]
            if filename[0] == '"' or filename[0] == "'":
                filename = filename[1:-1]
    elif response.url != url:
        filename = url2name(response.url)
    ext = os.path.splitext(filename)[1]
    if not ext: ext = DEFAULT_EXT
    return ext

def url2name(url):
    return os.path.basename(urllib.unquote(urlparse.urlsplit(url)[2]))
