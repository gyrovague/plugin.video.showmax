import re

from matthuisman import plugin, gui, cache, settings, userdata
from matthuisman.util import get_string as _

from .api import API

L_LOGIN            = 30000
L_HIDE_CHANNEL     = 30001
L_LOGOUT           = 30002
L_SETTINGS         = 30003
L_ASK_USERNAME     = 30004
L_ASK_PASSWORD     = 30005
L_LOGIN_ERROR      = 30006
L_LOGOUT_YES_NO    = 30007
L_NO_CHANNEL       = 30008
L_NO_STREAM        = 30009
L_ADOBE_ERROR      = 30010

def sorted_nicely(l):
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key['title'])]
    return sorted(l, key = alphanum_key)

api = API()

@plugin.before_dispatch()
def before_dispatch():
    api.new_session()
    plugin.logged_in = api.logged_in
    cache.enabled    = settings.getBool('use_cache', True)

@plugin.route('')
def home():
    folder = plugin.Folder()

    if not api.logged_in:
        folder.add_item(label=_(L_LOGIN), path=plugin.url_for(login))

    hidden = userdata.get('hidden', [])

    channels = sorted_nicely(api.channels().values())
    for channel in channels:
        if channel['title'] in hidden:
            continue

        folder.add_item(
            label = channel['title'],
            art   = {'thumb': channel['image']},
            path  = plugin.url_for(play, is_live=True, channel=channel['title']),
            info  = {'description': channel['description']},
            playable = True,
            context = ((_(L_HIDE_CHANNEL), 'XBMC.RunPlugin({})'.format(plugin.url_for(hide_channel, channel=channel['title']))),),
        )

    if api.logged_in:
        folder.add_item(label=_(L_LOGOUT), path=plugin.url_for(logout))

    folder.add_item(label=_(L_SETTINGS), path=plugin.url_for(plugin.ROUTE_SETTINGS))

    return folder

@plugin.route()
def login():
    while not api.logged_in:
        username = gui.input(_(L_ASK_USERNAME), default=userdata.get('username', '')).strip()
        if not username:
            break

        userdata.set('username', username)

        password = gui.input(_(L_ASK_PASSWORD), default=cache.get('password', '')).strip()
        if not password:
            break

        cache.set('password', password, expires=60)

        try:
            api.login(username=username, password=password)
        except Exception as e:
            gui.ok(_(L_LOGIN_ERROR, error_msg=e))

    cache.delete('password')

@plugin.route()
def logout():
    if not gui.yes_no(_(L_LOGOUT_YES_NO)):
        return

    api.logout()

@plugin.route()
def hide_channel(channel):
    hidden = userdata.get('hidden', [])

    if channel not in hidden:
        hidden.append(channel)

    userdata.set('hidden', hidden)
    gui.refresh()

@plugin.route()
@plugin.login_required()
def play(channel):
    use_ia_hls  = settings.getBool('use_ia_hls')

    channels = api.channels()
    channel = channels.get(channel)
    if not channel:
        raise plugin.Error(_(L_NO_CHANNEL))

    url = api.play_url(channel['url'])

    if not url:
        if gui.yes_no(_(L_NO_STREAM)):
            hide_channel(channel['title'])

    elif 'faxs' in url:
        if gui.yes_no(_(L_ADOBE_ERROR)):
            hide_channel(channel['title'])
            
    else:
        return plugin.PlayerItem(
            label = channel['title'],
            art   = {'thumb': channel['image']},
            info  = {'description': channel['description']},
            path  = url,
        )