import hashlib

from bs4 import BeautifulSoup

from matthuisman import userdata
from matthuisman.session import Session
from matthuisman.log import log

from .constants import HEADERS, API_URL, LOGIN_URL

class Error(Exception):
    pass

class API(object):
    def new_session(self):
        self.logged_in = False
        self._session = Session(HEADERS, base_url=API_URL)
        self.set_access_token(userdata.get('access_token'))

    def set_access_token(self, token):
        if token:
            self._session.headers.update({'Authorization': 'Bearer {0}'.format(token)})
            self.logged_in = True
        
    def login(self, username, password):
        log('API: Login')

        data = {
            'response_type': 'token',
            'lang': 'eng'
        }

        resp = self._session.get(LOGIN_URL, params=data)
        soup = BeautifulSoup(resp.text, 'html.parser')

        form = soup.find('form', id='new_signin')
        for e in form.find_all('input'):
            data[e.attrs['name']] = e.attrs.get('value')

        data.update({
            'signin[email]': username,
            'signin[password]': password,
        })

        resp = self._session.post(LOGIN_URL, data=data, allow_redirects=False)
        access_token = resp.cookies.get('showmax_oauth')
        
        if not access_token:
            self.logout()
            raise Error()

        self.set_access_token(access_token)

        data = self._session.get('user/current', params={'lang':'eng'}).json()
        if 'error_code' in data:
            raise Error()

        device_id = hashlib.sha1(username).hexdigest().upper()

        userdata.set('device_id', device_id)
        userdata.set('access_token', access_token)
        userdata.set('user_id', data['user_id'])

    def catalogue(self, _params):
        start = 0
        num   = 60
        items = []

        while True:
            params = {
                'field[]': ['id', 'images', 'title', 'items', 'total', 'type', 'description', 'videos'],
                'lang': 'eng',
                'num': num,
                'showmax_rating': 'adults',
                'sort': 'alphabet',
                'start': start,
                'subscription_status': 'full'
            }

            params.update(_params)

            data = self._session.get('catalogue/assets', params=params).json()
            items.extend(data['items'])
            if data['count'] < num or data['remaining'] == 0:
                break

            start += num

        return items

    def shows(self):
        return self.catalogue({
            'type': 'tv_series',
            'exclude_section[]': ['kids'],
        })

    def show(self, show_id):
        params = {
            'field[]': ['id', 'images', 'title', 'items', 'total', 'type', 'description', 'videos', 'number', 'seasons', 'episodes'],
         #   'expand_seasons': True,
            'lang': 'eng',
            'showmax_rating': 'adults',
            'subscription_status': 'full'
        }

        return self._session.get('catalogue/tv_series/{}'.format(show_id), params=params).json()

    def movies(self):
        return self.catalogue({
            'type': 'movie',
            'exclude_section[]': ['kids'],
        })

    def kids(self):
        return self.catalogue({
            'section': 'kids',
        })

    def logout(self):
        log('API: Logout')
        userdata.delete('device_id')
        userdata.delete('access_token')
        userdata.delete('user_id')
        self.new_session()

    def play(self, video_id):
        params = {
            'encoding': 'mpd_widevine_modular',
            'subscription_status': 'full',
            'lang': 'eng',
        }

        data = self._session.get('playback/play/{0}'.format(video_id), params=params).json()
        
        url        = data['url']
        task_id    = data['packaging_task_id']
        session_id = data['session_id']

        data = {
            'user_id': userdata.get('user_id'),
            'video_id': video_id,
            'hw_code': userdata.get('device_id'),
            'packaging_task_id': task_id,
            'session_id': session_id,
        }

        params = {'showmax_rating': 'adults', 'lang': 'eng'}
        data = self._session.post('playback/verify', params=params, data=data).json()

        license_request = data['license_request']
        license_url = API_URL.format('drm/widevine_modular?license_request={0}'.format(license_request))

        return url, license_url