import xbmc
import xbmcaddon

addon = xbmcaddon.Addon()
name = addon.getAddonInfo('name')

LOGDEBUG = xbmc.LOGDEBUG
LOGERROR = xbmc.LOGERROR
LOGFATAL = xbmc.LOGFATAL
LOGINFO = xbmc.LOGINFO
LOGNONE = xbmc.LOGNONE
LOGNOTICE = xbmc.LOGINFO #as per https://codedocs.xyz/xbmc/xbmc/python_v19.html
LOGSEVERE = xbmc.LOGFATAL #dito
LOGWARNING = xbmc.LOGWARNING

def log(msg, level=LOGNOTICE):
    # override message level to force logging when addon logging turned on
    if addon.getSetting('addon_debug') == 'true' and level == LOGDEBUG:
        level = LOGNOTICE
    
    try:
        if isinstance(msg, unicode):
            msg = '%s (ENCODED)' % (msg.encode('utf-8'))

        xbmc.log('%s: %s' % (name, msg), level)
    except Exception as e:
        try: xbmc.log('Logging Failure: %s' % (e), level)
        except: pass  # just give up
