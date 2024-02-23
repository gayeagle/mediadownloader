import json
import os
import platform
import requests
import sys

from io import BytesIO
from pathlib import Path
from tarfile import TarFile
from typing import Type
from zipfile import ZipFile

class _Browser():
    def __init__(self, api: str, drivername: str, config: str) -> None:
        self.api = api
        self.drivername = drivername
        self.config = config
    
    @staticmethod
    def get_download_url(config_json: dict, machine_type: str) -> str:
        return ''
    
    @staticmethod
    def get_id(config_json: dict) -> str:
        return ''

class Firefox(_Browser):
    def __init__(self) -> None:
        api = 'https://api.github.com/repos/mozilla/geckodriver/releases/latest'
        super().__init__(api, 'geckodriver.exe', 'firefox.json')
    
    @staticmethod
    def get_download_url(config_json: dict, machine_type: str) -> str:
        url = ''
        for asset in config_json['assets']:
            url = asset['browser_download_url']
            if machine_type in url and not 'asc' in url:
                break
        return url
    
    @staticmethod
    def get_id(config_json: dict) -> str:
        return config_json['id']
    
class Chrome(_Browser):
    def __init__(self) -> None:
        api = 'https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json'
        super().__init__(api, 'chromedriver.exe', 'chrome.json')
    
    @staticmethod
    def get_download_url(config_json: dict, machine_type: str) -> str:
        stable_drivers = config_json['channels']['Stable']['downloads']['chromedriver']
        url = ''
        if machine_type == 'macos':
            machine_type = 'mac'
        elif machine_type == 'macos-aarch64':
            machine_type = 'mac-arm64'
        for asset in stable_drivers:
            if machine_type in asset['url']:
                url = asset['url']
                break
        return url
    
    @staticmethod
    def get_id(config_json: dict) -> str:
        return config_json['channels']['Stable']['version']+config_json['channels']['Stable']['revision']

def platform_detect() -> str:
    is_64bits = sys.maxsize > 2**32
    system = platform.system()
    machine = platform.machine()
    if system == 'Windows':
        if is_64bits:
            if 'aarch64' in machine:
                return 'win-aarch64'
            return 'win64'
        return 'win32'
    if system == 'Linux':
        if is_64bits:
            if 'aarch64' in machine:
                return 'linux-aarch64'
            return 'linux64'
        return 'linux32'
    if system == 'Darwin':
        if 'aarch64' in machine:
            return 'macos-aarch64'
        return 'macos'
    return ''

def driver_update(browser: Type[_Browser]) -> bool:
    config = Path('drivers')/browser.config
    api = browser.api
    driver = Path('drivers')/browser.drivername
    if not config.exists():
        try:
            config_json = requests.get(api).json()
        except Exception as ex:
            print('Update Failed - Unable to fetch API information')
            print(ex)
            return False
        with config.open(mode='w') as cfg:
            cfg.write(json.dumps(config_json, indent=1))
    else:
        config_json = json.loads(config.read_text())
        latest_config = requests.get(api).json()
        if not browser.get_id(config_json) == browser.get_id(latest_config):
            with config.open(mode='w') as cfg:
                cfg.write(json.dumps(latest_config, indent=1))
    machine_type = platform_detect()
    if machine_type == '':
        print('Error: Unsupported CPU/Unknown CPU Type')
        print(machine_type)
        return False
    url = browser.get_download_url(config_json, machine_type)
    if url == '':
        print('Error: No supported download URL for machine type')
        print(machine_type)
        return False
    print(f'Detected machine type: {machine_type}\r\nFetching update from: {url}')
    r = requests.get(url)
    try:
        r.raise_for_status()
    except Exception as ex:
        print('Unable to fetch driver from URL')
        print('URL: '+url)
        print(ex)
        return False
    compressed = r.content
    if 'zip' in url:
        with ZipFile(BytesIO(compressed)) as unzip:
            for zip_info in unzip.infolist():
                if zip_info.is_dir():
                    continue
                if browser.drivername in zip_info.filename:
                    driver.write_bytes(unzip.read(zip_info))
                    break
    elif 'tar.gz' in url:
        with TarFile(BytesIO(compressed), mode='r|gz') as untar:
            #TODO - Tar file extraction of Chrome drivers probably doesn't work - fix
            untar.extract(browser.drivername, path=driver, filter='data')
    else:
        print('Error: Unknown file compression format')
        print('URL: '+url)
        return False
    return True
    
def add_to_path() -> None:
    driver_path = Path('./drivers').resolve()
    system_path = [Path(p) for p in os.environ['PATH'].split(';')]
    if not driver_path in system_path:
        os.environ['PATH'] += os.pathsep + str(driver_path)