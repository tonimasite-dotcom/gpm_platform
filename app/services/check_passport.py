import asyncio
import json
import os
import sys
import time
import traceback
from datetime import timedelta, datetime
from threading import Thread
from typing import Optional

import aiohttp
from loguru import logger
from pyvirtualdisplay import Display
from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class UnauthorizedError(Exception):
    pass


class ServiceNotAvailable(Exception):
    pass


class GosuslugiResponse:
    def __init__(self, status: bool, internal_error: bool):
        self.status = status
        self.internal_error = internal_error


class PassportChecker(metaclass=Singleton):
    def __init__(self, debug: bool = False):
        self._cookies: dict = {}
        self._get_credentials_busy: bool = False
        self._queue: list[str] = []
        self._last_time_request: datetime = datetime.now() - timedelta(seconds=20)
        self._debug: bool = debug

    async def _check_passport(self, series: int, number: int, firstname: str, lastname: str) -> bool:
        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'ru-RU,ru;q=0.9,es-RU;q=0.8,es;q=0.7,en-RU;q=0.6,en;q=0.5,zh-RU;q=0.4,zh;q=0.3,en-US;q=0.2',
            'content-type': 'application/json',
            'origin': 'https://www.gosuslugi.ru',
            'referer': 'https://www.gosuslugi.ru/621102/1/form',
            'sec-ch-ua': '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        }

        json_data = {
            'scenarioDto': {
                'serviceCode': '60021102',
                'targetCode': '-60021102',
                'currentScenarioId': 1,
                'serviceDescriptorId': '60021102',
                'currentUrl': 'https://www.gosuslugi.ru/621102/1/form',
                'finishedAndCurrentScreens': [
                    's1',
                    's3',
                    's_redirect',
                ],
                'cachedAnswers': {},
                'currentValue': {
                    'redirect_component': {
                        'visited': True,
                        'value': '',
                    },
                },
                'errors': {},
                'uniquenessErrors': [],
                'applicantAnswers': {
                    'w1': {
                        'visited': True,
                        'value': '',
                    },
                    'pd1': {
                        'visited': True,
                        'value': f'{{"series": "{series}","number":"{number}","date":"","emitter":null,"issueId":null}}',
                    },
                    'component_lastname': {
                        'visited': True,
                        'value': f'{lastname}',
                    },
                    'component_firstname': {
                        'visited': True,
                        'value': f'{firstname}',
                    },
                    'check_limit': {
                        'visited': True,
                        'value': '{"statusCode":200}',
                    },
                },
                'cycledApplicantAnswers': {
                    'inCycle': False,
                    'answerlist': [],
                },
                'participants': {},
                'display': {
                    'id': 's_redirect',
                    'name': 'Перенаправление дальше по сценарию',
                    'type': 'EMPTY',
                    'header': '',
                    'components': [
                        {
                            'id': 'redirect_component',
                            'name': '',
                            'type': 'Redirect',
                            'label': '',
                            'skipValidation': False,
                            'attrs': {
                                'actions': [
                                    {
                                        'label': '',
                                        'value': '',
                                        'type': 'nextStep',
                                        'action': 'getNextScreen',
                                    },
                                ],
                                'act': 'Перенаправление по action',
                                'refs': {},
                            },
                            'arguments': {},
                            'value': '',
                            'required': True,
                            'sendAnalytics': False,
                        },
                    ],
                    'buttons': [],
                    'hideBackButton': False,
                    'infoComponents': [],
                    'logicAfterValidationComponents': [
                        {
                            'id': 'trobber',
                            'name': '',
                            'type': 'RestCall',
                            'label': '',
                            'skipValidation': False,
                            'attrs': {
                                'onload': {
                                    'trobber': {
                                        'timeout': 20,
                                    },
                                },
                                'url': '',
                                'method': 'POST',
                                'path': '',
                                'headers': {
                                    'Accept': '',
                                    'Content-Type': '',
                                },
                                'body': '',
                                'refs': {},
                            },
                            'arguments': {},
                            'value': '{"id":"trobber","method":"POST","url":"https://www.gosuslugi.ru","body":"","serviceId":"60021102","headers":{"Accept":"","Content-Type":""},"cookies":{},"formData":{},"filteredHealthArgs":{}}',
                            'required': True,
                            'sendAnalytics': False,
                        },
                    ],
                    'notSendToSp': False,
                    'forceSendToSuggestions': False,
                    'needToUpdateAdditionalParameters': False,
                    'forceDeliriumCall': False,
                    'checkSendPermission': False,
                    'arguments': {},
                    'acceptCookies': [],
                    'accepted': True,
                    'firstScreen': False,
                    'terminal': False,
                    'impasse': False,
                },
                'logicComponents': [
                    {
                        'id': 'check_limit',
                        'name': '',
                        'type': 'BackRestCall',
                        'label': '',
                        'skipValidation': False,
                        'attrs': {},
                        'arguments': {},
                        'value': '{"statusCode":200}',
                        'required': True,
                        'sendAnalytics': False,
                    },
                ],
                'serviceInfo': {
                    'department': {
                        'id': '10000001197',
                        'title': 'Министерство внутренних дел Российской Федерации',
                    },
                    'error': 'Region not found',
                    'orderType': 'ORDER',
                    'queryParams': {},
                    'formId': 'form',
                    'proactivityCreated': False,
                    'deviceType': 'desk',
                    'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                },
                'signInfoMap': {},
                'attachmentInfo': {},
                'additionalParameters': {},
                'serviceParameters': {},
                'generatedFiles': [],
                'disclaimers': [],
                'fileGenerateActions': [],
                'cycledApplicantAnswerContext': {},
                'gender': 'M',
            },
            'isInviteScenario': False,
            'canStartNew': False,
            'health': {
                'dictionaries': [
                    {
                        'id': 'check_limit',
                        'method': 'GET',
                        'status': 'OK',
                        'args': {},
                    },
                ],
            },
        }
        print('req')
        async with aiohttp.ClientSession(headers=headers, cookies=self._cookies) as session:
            async with session.post(
                    'https://www.gosuslugi.ru/api/service/60021102/scenario/getNextStep',
                    data=json.dumps(json_data),
                    proxy=GOSUSLUGI_HTTP_PROXY,
                    timeout=10
            ) as response:

                print('enc_req')

                if 'UNAUTHORIZED' in await response.text():
                    raise UnauthorizedError()

                print(await response.json())
                if 'Действительный' in (await response.json())['scenarioDto']['logicComponents'][0]['value']:
                    return True
                elif 'Entity not found' in (await response.json())['scenarioDto']['logicComponents'][0]['value']:
                    return False
                else:
                    raise ServiceNotAvailable()

    async def _check_passport_wrapper(
            self, series: int, number: int, firstname: str, lastname: str) -> GosuslugiResponse:
        try:
            result: bool = await self._check_passport(series, number, firstname, lastname)
            return GosuslugiResponse(status=result, internal_error=False)
        except UnauthorizedError:
            logger.debug('get gosuslugi credentials')
            await self._update_credentials()

            try:
                result: bool = await self._check_passport(series, number, firstname, lastname)
                return GosuslugiResponse(status=result, internal_error=False)
            except Exception as e:
                logger.error(traceback.format_exc())
        except Exception as e:
            logger.error(traceback.format_exc())

        return GosuslugiResponse(status=False, internal_error=True)

    def _get_credentials_wrapper(self) -> None:
        try:
            self._get_credentials()
        except Exception as e:
            logger.error(traceback.format_exc())

    def _get_credentials(self) -> None:
        options = webdriver.ChromeOptions()

        if not self._debug:
            display = Display(visible=0, size=(800, 600))
            display.start()
        # options.add_argument("--headless")
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(f'--remote-debugging-port=9200')

        options.add_argument("--disable-gpu")
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("excludeSwitches", ["disable-popup-blocking"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("start-maximized")
        options.page_load_strategy = 'eager'
        prefs = {"profile.managed_default_content_settings.images": 1}
        options.add_experimental_option("prefs", prefs)

        seleniumwire_options = {
            'proxy': {
                'http': GOSUSLUGI_HTTP_PROXY,
                'https': GOSUSLUGI_HTTP_PROXY,
            }
        }
        if self._debug:
            service = Service(ChromeDriverManager().install())
        else:
            service = Service('/usr/local/bin/chromedriver')
        driver = webdriver.Chrome(
            service=service, options=options, seleniumwire_options=seleniumwire_options
        )

        driver.get('https://esia.gosuslugi.ru/login/')
        time.sleep(10)

        driver.save_screenshot('gosuslugi_before_login.png')

        driver.find_element(By.ID, 'login').send_keys(GOSUSLUGI_LOGIN)
        driver.find_element(By.ID, 'password').send_keys(GOSUSLUGI_PASSWORD)
        driver.find_element(By.CLASS_NAME, 'plain-button_wide').click()
        time.sleep(10)

        driver.save_screenshot('gosuslugi_after_login.png')

        with open('gosuslugi_after_login.html', 'w') as f:
            f.write(driver.page_source)

        driver.get('https://www.gosuslugi.ru/621102/1/form')
        time.sleep(6)
        driver.save_screenshot('gosuslugi_in_form.png')

        result = {}
        cookies: list[dict] = driver.get_cookies()
        for cookie in cookies:
            result[cookie['name']] = cookie['value']

        self._cookies = result
        driver.quit()
        if not self._debug:
            display.stop()

    async def _update_credentials(self) -> None:
        if not self._get_credentials_busy:
            self._get_credentials_busy = True
            thread: Thread = Thread(target=self._get_credentials_wrapper(), args=())
            thread.start()
            while thread.is_alive():
                logger.debug('wait credentials')
                await asyncio.sleep(10)

            self._get_credentials_busy = False

    async def check_status(self,
                           user_tg_id: str,
                           series: int,
                           number: int,
                           firstname: str,
                           lastname: str) -> Optional[GosuslugiResponse]:
        if user_tg_id in self._queue:
            return None
        self._queue.append(user_tg_id)

        while (self._queue[0] != user_tg_id or
               self._get_credentials_busy or
               self._last_time_request + timedelta(seconds=20) > datetime.now()):
            await asyncio.sleep(1)

        result: GosuslugiResponse = await self._check_passport_wrapper(series, number, firstname, lastname)

        self._last_time_request = datetime.now()
        self._queue.remove(user_tg_id)
        return result


async def main():
    print(await PassportChecker(debug=True).check_status('1', 1111, 111111, 'Иван', 'Иванов'))

if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.realpath(__file__))
    parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    main_dir = os.path.abspath(os.path.join(parent_dir, os.pardir))
    sys.path.append(main_dir)

    from app.dependencies import GOSUSLUGI_LOGIN, GOSUSLUGI_PASSWORD, GOSUSLUGI_HTTP_PROXY

    asyncio.run(main())
else:
    from app.dependencies import GOSUSLUGI_LOGIN, GOSUSLUGI_PASSWORD, GOSUSLUGI_HTTP_PROXY

