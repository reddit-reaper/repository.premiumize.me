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
import sys
import os.path
from local_lib.url_dispatcher import URL_Dispatcher
from local_lib.premiumize_api import Premiumize_API, PremiumizeError, DOWN_TYPES
from local_lib import log_utils
from local_lib import kodi
from local_lib import utils
from local_lib.kodi import i18n
import xbmcgui
import xbmcplugin
import xbmcvfs

def __enum(**enums):
    return type('Enum', (), enums)

VIDEO_EXTS = ['MP4', 'MKV', 'AVI']
STATUS_COLORS = {'FINISHED': 'green', 'WAITING': 'blue', 'SEEDING': 'green', 'TIMEOUT': 'red', 'ERROR': 'red'}
DEFAULT_COLOR = 'white'
MODES = __enum(
    MAIN='main', TRANSFER_LIST='transfer_list', FILE_LIST='file_list', BROWSE_TORRENT='browse_torrent', PLAY_VIDEO='play_video',
    CLEAR_FINISHED='clear_finished', DELETE_TRANSFER='delete_transfer', DELETE_ITEM='delete_item', CREATE_FOLDER='create_folder',
    DELETE_FOLDER='delete_folder', RENAME_FOLDER='rename_folder', ADD_DOWNLOAD='add_download', DOWNLOAD_ITEM='download_item',
    DOWNLOAD_VIDEO='download_video', PASTE_TORRENT='paste_torrent'
)

customer_id = kodi.get_setting('customer_id')
pin = kodi.get_setting('pin')
use_https = kodi.get_setting('use_https') == 'true'
premiumize_api = Premiumize_API(customer_id, pin, use_https)
url_dispatcher = URL_Dispatcher()

@url_dispatcher.register(MODES.MAIN)
def main_menu():
    kodi.create_item({'mode': MODES.TRANSFER_LIST}, i18n('transfer_list'))
    queries = {'mode': MODES.CREATE_FOLDER, 'parent_id': None}
    menu_items = [(i18n('create_folder'), 'RunPlugin(%s)' % (kodi.get_plugin_url(queries)))]
    kodi.create_item({'mode': MODES.FILE_LIST}, i18n('file_list'), menu_items=menu_items)
    kodi.create_item({'mode': MODES.ADD_DOWNLOAD}, i18n('add_download'))
    kodi.create_item({'mode': MODES.PASTE_TORRENT}, i18n('paste_torrent'))
    kodi.end_of_directory()

@url_dispatcher.register(MODES.PASTE_TORRENT)
def paste_torrent():
    torrent = kodi.get_keyboard(i18n('paste_keyboard'))
    if torrent:
        add_download(torrent, torrent)

@url_dispatcher.register(MODES.ADD_DOWNLOAD)
def add_download_file():
    dialog = xbmcgui.Dialog()
    path = dialog.browse(1, i18n('select_torrent_nzb'), 'files', '.torrent|.magnet|.link|.nzb')
    if path:
        f = xbmcvfs.File(path, 'rb')
        download = f.read()
        f.close()
        if download.endswith('\n'):
            download = download[:-1]
        add_download(download, path)
            
def add_download(download, path):
    if download:
        try:
            file_name = os.path.basename(path)
            download_type = DOWN_TYPES.NZB if path.lower().endswith('nzb') else DOWN_TYPES.TORRENT
            premiumize_api.add_download(download, download_type, file_name=file_name)
            msg = '%s: %s' % (i18n('download_added'), file_name)
        except PremiumizeError as e:
            msg = str(e)
        kodi.notify(msg=msg, duration=5000)
    
@url_dispatcher.register(MODES.TRANSFER_LIST)
def show_transfers():
    results = premiumize_api.get_transfers()
    kodi.create_item({'mode': MODES.CLEAR_FINISHED}, i18n('clear_all_finished'), is_folder=False, is_playable=False)
    if 'transfers' in results:
        for item in results['transfers']:
            status = item['status'].upper()
            color = STATUS_COLORS.get(status, DEFAULT_COLOR)
            label = '[[COLOR %s]%s[/COLOR]] %s' % (color, status, item['name'])
            if 'size' in item: label += ' (%s)' % (utils.format_size(int(item['size']), 'B'))
            if item['status'] != 'finished':
                try: progress = item['progress'] * 100
                except: progress = 0
                if 'progress' in item: label += ' (%d%% %s)' % (progress, i18n('complete'))
                if 'eta' in item and item['eta']: label += ' - ETA: %s' % (utils.format_time(item['eta']))
                next_mode = MODES.TRANSFER_LIST
                del_label = i18n('abort_transfer')
            else:
                next_mode = MODES.BROWSE_TORRENT
                del_label = i18n('del_transfer')
            queries = {'mode': MODES.DELETE_TRANSFER, 'torrent_id': item['id']}
            menu_items = [(del_label, 'RunPlugin(%s)' % (kodi.get_plugin_url(queries)))]
            kodi.create_item({'mode': MODES.FILE_LIST, 'folder_id': item['folder_id'], 'torrent_id': item['id']}, label, menu_items=menu_items)
            
    kodi.set_content('files')
    kodi.end_of_directory()

@url_dispatcher.register(MODES.DELETE_ITEM, ['torrent_id'])
def delete_item(torrent_id):
    premiumize_api.delete_item(torrent_id)
    kodi.refresh_container()

@url_dispatcher.register(MODES.DELETE_TRANSFER, ['torrent_id'])
def delete_transfer(torrent_id):
    premiumize_api.delete_transfer(torrent_id)
    kodi.refresh_container()

@url_dispatcher.register(MODES.DELETE_FOLDER, ['folder_id'])
def delete_folder(folder_id):
    premiumize_api.delete_folder(folder_id)
    kodi.refresh_container()

@url_dispatcher.register(MODES.CREATE_FOLDER, ['mode'], ['folder_id'])
@url_dispatcher.register(MODES.RENAME_FOLDER, ['mode', 'folder_id', 'folder_name'])
def folder_action(mode, folder_id=None, folder_name=None):
    if mode == MODES.RENAME_FOLDER and folder_name is not None:
        default = folder_name
    else:
        default = ''

    folder_name = kodi.get_keyboard(i18n('enter_folder_name'), default)
    if folder_name:
        if mode == MODES.CREATE_FOLDER:
            premiumize_api.create_folder(folder_name, folder_id)
        elif mode == MODES.RENAME_FOLDER:
            premiumize_api.rename_folder(folder_name, folder_id)
            kodi.refresh_container()

@url_dispatcher.register(MODES.CLEAR_FINISHED)
def clear_finished():
    premiumize_api.clear_finished()
    kodi.refresh_container()

@url_dispatcher.register(MODES.FILE_LIST, [], ['folder_id'])
def show_files(folder_id=None):
    results = premiumize_api.get_files(folder_id)
    if 'content' in results:
        for result in results['content']:
            if result['type'] == 'folder':
                menu_items = []
                queries = {'mode': MODES.CREATE_FOLDER, 'folder_id': result['id']}
                menu_items.append((i18n('create_folder'), 'RunPlugin(%s)' % (kodi.get_plugin_url(queries))))
                queries = {'mode': MODES.DELETE_FOLDER, 'folder_id': result['id']}
                menu_items.append((i18n('delete_folder'), 'RunPlugin(%s)' % (kodi.get_plugin_url(queries))))
                queries = {'mode': MODES.RENAME_FOLDER, 'folder_id': result['id'], 'folder_name': result['name']}
                menu_items.append((i18n('rename_folder'), 'RunPlugin(%s)' % (kodi.get_plugin_url(queries))))
                
                kodi.create_item({'mode': MODES.FILE_LIST, 'folder_id': result['id']}, result['name'], menu_items=menu_items)
            elif result['type'] == 'torrent':
                label = result['name']
                if 'size' in result and result['size']:
                    label += ' (%s)' % (utils.format_size(int(result['size']), 'B'))
                menu_items = []
                queries = {'mode': MODES.DOWNLOAD_ITEM, 'hash_id': result['hash'], 'name': result['name']}
                menu_items.append((i18n('download_item'), 'RunPlugin(%s)' % (kodi.get_plugin_url(queries))))
                queries = {'mode': MODES.DELETE_ITEM, 'torrent_id': result['id']}
                menu_items.append((i18n('delete_item'), 'RunPlugin(%s)' % (kodi.get_plugin_url(queries))))
                kodi.create_item({'mode': MODES.BROWSE_TORRENT, 'hash_id': result['hash'], 'torrent_id': result['id']}, label, menu_items=menu_items)
            elif result['type'] == 'file':
                menu_items=[]
                kodi.create_item({'mode': MODES.PLAY_VIDEO, 'name': result['name'], 'url': result['link']}, result['name'], is_folder=False, is_playable=True, menu_items=menu_items)
                
    kodi.set_content('files')
    kodi.end_of_directory()

@url_dispatcher.register(MODES.DOWNLOAD_ITEM, ['hash_id', 'name'])
def download_item(hash_id, name):
    results = premiumize_api.browse_torrent(hash_id)
    if 'zip' in results:
        file_name = name if name.endswith('.zip') else name + '.zip'
        download(results['zip'], file_name)

@url_dispatcher.register(MODES.DOWNLOAD_VIDEO, ['url', 'name'])
def download_video(url, name):
    download(url, name)

def download(url, file_name):
    path = ''
    if kodi.get_setting('down_prompt') == 'true':
        dialog = xbmcgui.Dialog()
        path = dialog.browse(3, i18n('select_directory'), 'files')
    else:
        path = kodi.get_setting('down_folder')
        
    if path:
        utils.download_media(url, path, file_name)

@url_dispatcher.register(MODES.BROWSE_TORRENT, ['hash_id'])
def browse_torrent(hash_id):
    results = premiumize_api.browse_torrent(hash_id)
    if 'content' in results:
        videos = get_videos(results['content'])
        for video in sorted(videos, key=lambda x: x['label']):
            menu_items = []
            queries = {'mode': MODES.DOWNLOAD_VIDEO, 'url': video['url'], 'name': video['name']}
            menu_items.append((i18n('download_video'), 'RunPlugin(%s)' % (kodi.get_plugin_url(queries))))
            kodi.create_item({'mode': MODES.PLAY_VIDEO, 'name': video['name'], 'url': video['url']}, video['label'], is_folder=False, is_playable=True, menu_items=menu_items)
            
    kodi.set_content('files')
    kodi.end_of_directory()


@url_dispatcher.register(MODES.PLAY_VIDEO, ['url'], ['name'])
def play_video(url, name=None):
    listitem = xbmcgui.ListItem(label=name, path=url)
    listitem.setPath(url)
    if name is not None:
        info = utils.make_info(name)
        listitem.setInfo('video', info)
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

def get_videos(content, parent=None):
    videos = []
    show_transcodes = kodi.get_setting('show_transcode') == 'true'
    try: min_duration = int(kodi.get_setting('duration_filter')) * 60
    except: min_duration = 0
    exclusion_list = utils.make_excl_list()
    for item in content.itervalues():
        if parent is None:
            label = item['name']
        else:
            label = parent + '/' + item['name']
            
        if item['type'] == 'dir':
            videos += get_videos(item['children'], label)
        else:
            if 'ext' in item and item['ext'].upper() in VIDEO_EXTS:
                if any([excl for excl in exclusion_list if excl in item['name'].upper()]):
                    log_utils.log('Excluding %s matching %s' % (item['name'], exclusion_list), log_utils.LOGDEBUG)
                    continue
                
                try: duration = float(item['duration'])
                except: duration = min_duration
                if min_duration and duration < min_duration:
                    log_utils.log('Excluding: %s %s < %s' % (item['name'], item['duration'], min_duration), log_utils.LOGDEBUG)
                    continue
                
                if 'size' in item: label += ' (%s)' % (utils.format_size(int(item['size']), 'B'))
                video = {'label': label, 'name': item['name'], 'url': item['url']}
                videos.append(video)
                if show_transcodes and 'transcoded' in item and item['transcoded']:
                    transcode = item['transcoded']
                    try: duration = float(transcode['duration'])
                    except: duration = min_duration
                    if min_duration and duration < min_duration:
                        log_utils.log('Excluding(T): %s %s < %s' % (item['name'], transcode['duration'], min_duration), log_utils.LOGDEBUG)
                        continue
                    
                    label = '%s (%s) (%s)' % (label, i18n('transcode'), utils.format_size(int(transcode['size']), 'B'))
                    video = {'label': label, 'name': item['name'], 'url': transcode['url']}
                    videos.append(video)
    return videos

def main(argv=None):
    if sys.argv: argv = sys.argv
    queries = kodi.parse_query(sys.argv[2])
    log_utils.log('Version: |%s| Queries: |%s|' % (kodi.get_version(), queries))
    log_utils.log('Args: |%s|' % (argv))

    # don't process params that don't match our url exactly. (e.g. plugin://plugin.video.1channel/extrafanart)
    plugin_url = 'plugin://%s/' % (kodi.get_id())
    if argv[0] != plugin_url:
        return

    try:
        mode = queries.get('mode', None)
        url_dispatcher.dispatch(mode, queries)
    except PremiumizeError as e:
        log_utils.log('Premiumize Error: %s' % (str(e)), log_utils.LOGERROR)
        kodi.notify(msg=str(e), duration=7500)

if __name__ == '__main__':
    sys.exit(main())
