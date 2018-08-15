from matthuisman import plugin, gui, cache, settings, userdata, inputstream
from matthuisman.util import get_string as _

from .api import API
from .constants import LIST_EXPIRY, EPISODE_EXPIRY, THUMB_HEIGHT, FANART_HEIGHT

L_LOGIN            = 30000
L_LOGOUT           = 30002
L_SETTINGS         = 30003
L_ASK_USERNAME     = 30004
L_ASK_PASSWORD     = 30005
L_LOGIN_ERROR      = 30006
L_LOGOUT_YES_NO    = 30007
L_SHOWS            = 30008
L_MOVIES           = 30009
L_KIDS             = 30010
L_SEASON_NUMBER    = 30011
L_EPISODE_NUMBER   = 30012

api = API()

@plugin.before_dispatch()
def before_dispatch():
    api.new_session()
    plugin.logged_in = api.logged_in
    cache.enabled    = settings.getBool('use_cache', True)

@plugin.route('')
def home():
    folder = plugin.Folder(cacheToDisc=False)

    if not api.logged_in:
        folder.add_item(label=_(L_LOGIN, bold=True), path=plugin.url_for(login))

    folder.add_item(label=_(L_SHOWS, bold=True), path=plugin.url_for(shows), cache_key=cache.key_for(shows))
    folder.add_item(label=_(L_MOVIES, bold=True), path=plugin.url_for(movies), cache_key=cache.key_for(movies))
    folder.add_item(label=_(L_KIDS, bold=True), path=plugin.url_for(kids), cache_key=cache.key_for(kids))

    if api.logged_in:
        folder.add_item(label=_(L_LOGOUT), path=plugin.url_for(logout))

    folder.add_item(label=_(L_SETTINGS), path=plugin.url_for(plugin.ROUTE_SETTINGS))

    return folder

@plugin.route()
@cache.cached(LIST_EXPIRY)
def shows():
    folder = plugin.Folder(title=_(L_SHOWS))
    rows = api.shows()
    folder.add_items(_parse_rows(rows))
    return folder

@plugin.route()
@cache.cached(LIST_EXPIRY)
def movies():
    folder = plugin.Folder(title=_(L_MOVIES))
    rows = api.movies()
    folder.add_items(_parse_rows(rows))
    return folder

@plugin.route()
@cache.cached(LIST_EXPIRY)
def kids():
    folder = plugin.Folder(title=_(L_KIDS))
    rows = api.kids()
    folder.add_items(_parse_rows(rows))
    return folder

@plugin.route()
@cache.cached(EPISODE_EXPIRY)
def show(show_id):
    folder = plugin.Folder()

    data   = api.show(show_id)
    art    = _get_art(data['images'])
    folder.title = data['title']

    for season in data['seasons']:
        folder.add_item(
            label = _(L_SEASON_NUMBER, label=True, season_number=season['number']),
            art   = art,
            is_folder = False,
        )

        rows = season['episodes']
        folder.add_items(_parse_rows(rows, art))

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
        except Exception:
            gui.ok(_(L_LOGIN_ERROR))

    cache.delete('password')

@plugin.route()
def logout():
    if not gui.yes_no(_(L_LOGOUT_YES_NO)):
        return

    api.logout()

@plugin.route()
@plugin.login_required()
def play(video_id):
    url, license_url = api.play(video_id)
    return plugin.PlayerItem(inputstream=inputstream.Widevine(license_url), path=url)

def _parse_rows(rows, default_art=None):
    items = []

    for row in rows:
        item = plugin.Item(
            label    = row['title'],
            info     = {'plot': row['description']},
            art      = _get_art(row.get('images', []), default_art),
        )

        if row['type'] in ('movie', 'episode'):
            videos = _get_videos(row.get('videos', []))

            item.info.update({
                'duration': int(videos['main']['duration']),
                'mediatype': row['type'],
            })

            item.video = {'height': videos['main']['height'], 'width': videos['main']['width'], 'codec': 'h264'}
            item.path  = plugin.url_for(play, video_id=videos['main']['id'])
            item.playable = True

            if 'trailer' in videos:
                item.info['trailer'] = plugin.url_for(play, video_id=videos['trailer']['id'])

            if not item.label:
                item.label = _(L_EPISODE_NUMBER, episode_number=row['number'])

        elif row['type'] == 'tv_series':
            item.path      = plugin.url_for(show, show_id=row['id'])
            item.cache_key = cache.key_for(show, show_id=row['id'])

        items.append(item)

    return items

def _get_videos(videos):
    vids = {}

    for video in videos:
        if video['usage'] == 'main':
            vids['main'] = video
        elif video['usage'] == 'trailer':
            vids['trailer'] = video

    return vids

def _get_art(images, default_art=None):
    art = {}
    default_art = default_art or {}

    for image in images:
        if image['type'] == 'poster':
            if image['orientation'] == 'square' or 'thumb' not in art:
                art['thumb'] = image['link'] + '/x{}'.format(THUMB_HEIGHT)
        elif image['type'] == 'background':
            art['fanart'] = image['link'] + '/x{}'.format(FANART_HEIGHT)
        elif image['type'] == 'hero' and 'fanart' not in art:
            art['fanart'] = image['link'] + '/x{}'.format(FANART_HEIGHT)
        elif image['type'] == 'poster' and image['orientation'] == 'portrait':
            art['poster'] = image['link'] + '/x{}'.format(THUMB_HEIGHT)

    for key in default_art:
        if key not in art:
            art[key] = default_art[key]

    return art