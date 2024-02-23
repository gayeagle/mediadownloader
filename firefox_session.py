import configparser
import driver
import json
import os
import sqlite3
import time

from datetime import datetime
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class MozillaSession():
    def __init__(self) -> None:
        self.delay = 3
        self.use_x = False
        self.platform = driver.platform_detect()
        self.firefox_driver = driver.Firefox()
        now = datetime.now()
        self.cache_file = Path('./cache/cachelist.json')
        self.cache = json.loads(self.cache_file.read_text())
        if not 'driver_update' in self.cache or (now - datetime.fromisoformat(self.cache['driver_update'])).days > 0:
            print('Updating Driver...')
            driver.driver_update(self.firefox_driver)
            self.cache['driver_update'] = now.isoformat()
            with self.cache_file.open(mode='w') as cf:
                json.dump(self.cache, cf, indent=1)
        if not str(Path('./drivers').resolve()) in os.environ['PATH']:
            driver.add_to_path()
        self._get_session_cookies()
        self.cookie_jar = MozillaCookieJar(str(Path('./cache/cookiefile.txt')))
        self.cookie_jar.load()
        self.options = Options()
        self.options.add_argument('-headless')
        self.selenium_webdriver = webdriver.Firefox(options=self.options)
        self.url = 'twitter.com' if not self.use_x else 'x.com'
        self.selenium_webdriver.get('https://'+self.url)
        for cookie in self.cookie_jar:
            if self.url in cookie.domain:
                print('Adding Cookie:', cookie.name)
                self.selenium_webdriver.add_cookie({
                    'name': cookie.name,
                    'value': cookie.value,
                    'domain': cookie.domain,
                    'expiry': cookie.expires,
                    'secure': cookie.secure
                })
    
    def __delattr__(self, __name: str) -> None:
        if __name == 'selenium_webdriver':
            self.selenium_webdriver.quit()
        super().__delattr__(__name)

    def get_media_page(self, username: str):
        url = 'twitter.com/' if not self.use_x else 'x.com/'
        media_url = 'https://'+url+username+'/media'
        xpath = '/html/body/div[1]/div/div/div[2]/main/div/div/div/div/div/div[3]/div/div/section/div/div/div[3]/div/div/div/li[1]/div/div/div/a'
        self.selenium_webdriver.get(media_url)
        element = WebDriverWait(self.selenium_webdriver, 10).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        self.selenium_webdriver.save_screenshot('screenshot.png')
    
    def _get_session_cookies(self) -> None:
        session_path = None
        if 'win' in self.platform:
            session_path = Path(os.getenv('APPDATA'))/'Mozilla'/'Firefox'
        elif 'mac' in self.platform:
            session_path = Path('~/Library/Mozilla/Firefox')
        elif 'linux' in self.platform:
            session_path = Path('~/.mozilla/firefox')
        if not session_path:
            print(f'Error: Platform unsupported! Detected platform: {self.platform}')
            return
        if 'win' in self.platform:
            profile_config = configparser.ConfigParser()
            profile_config.read(str(session_path/'profiles.ini'))
            for s in profile_config.sections():
                if 'Name' in profile_config[s]:
                    if profile_config[s]['Name'] == 'default-release':
                        session_path /= profile_config[s]['Path']
                        break
        #TODO - Linux/Mac Profile Support
        cookie_db = session_path/'cookies.sqlite'
        if not cookie_db.exists():
            print(f'Error: Cookie DB not found at path "{str(session_path)}"')
            return
        con = sqlite3.connect('file:'+str(cookie_db)+'?mode=ro', uri=True)
        cur = con.execute('SELECT host, path, isSecure, expiry, name, value FROM moz_cookies '
                    'WHERE host LIKE "%twitter.com%" OR host LIKE "_x.com%" OR host LIKE "x.com%"')
        try:
            with Path('cache/cookiefile.txt').open('w') as cf:
                cf.write('# Netscape HTTP Cookie File\n')
                cf.write('# Made automatically - Don\'t edit unless you know what you\'re doing :)\n')
                for row in cur:
                    row = [str(r) for r in row]
                    wild = 'TRUE' if row[0][0] == '.' else 'FALSE'
                    secure = 'FALSE' if row[2] == '0' else 'TRUE'
                    cf.write('\t'.join([
                        row[0], wild, row[1], secure, row[3], row[4], row[5]
                    ]))
                    cf.write('\n')
        except Exception as ex:
            print('Error: Failed to properly read cookies DB.')
            print(ex)
        finally:
            con.close()

if __name__ == '__main__':
    ms = MozillaSession()
    print('Session Created')
    time.sleep(3)
    ms.get_media_page('NWStornado')
    del ms.selenium_webdriver