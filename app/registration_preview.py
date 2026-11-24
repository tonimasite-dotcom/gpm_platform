"""Isolated registration laboratory. No production account/profile APIs or DBs.

All phone challenges are simulated. Records in this private SQLite file can
never authenticate against GPM or subscribe to orders, messages or payments.
"""
import asyncio
from collections import deque
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
from threading import Lock
import time
import unicodedata
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, HTTPException, Request, Response

PREFIX = '/app-api/registration-preview'
FLOW_VERSION = 'preview-1'
MINIMUM_AGE = 18
MIDDLE_NAME_REQUIRED = False
AGE_TIMEZONE = 'Europe/Moscow'
TTL = 30 * 24 * 3600
TEST_CODE = '123456'
LOCATIONS = [
    {'id': 101, 'kind': 'city', 'name': 'Москва', 'enabled': True},
    {'id': 102, 'kind': 'city', 'name': 'Санкт-Петербург', 'enabled': True},
    {'id': 501, 'kind': 'district', 'city_id': 101, 'name': 'Северный округ', 'enabled': True},
    {'id': 502, 'kind': 'district', 'city_id': 102, 'name': 'Центральный район', 'enabled': True},
]
FIELDS = {'phone', 'phone_country', 'city_ids', 'district_ids', 'first_name',
          'last_name', 'middle_name', 'birth_date', 'citizenship_ru', 'has_straps', 'has_tools'}
SCHEMA = """
CREATE TABLE IF NOT EXISTS preview_sessions (
 id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, answers TEXT NOT NULL,
 revision INTEGER NOT NULL, created REAL NOT NULL, updated REAL NOT NULL, expires REAL NOT NULL,
 verified_phone TEXT, challenge_phone TEXT, challenge_sent REAL, challenge_until REAL,
 attempts INTEGER NOT NULL DEFAULT 0, profile_id TEXT, complete_key TEXT, complete_revision INTEGER
);
CREATE TABLE IF NOT EXISTS preview_profiles (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL UNIQUE, phone TEXT NOT NULL UNIQUE,
 answers TEXT NOT NULL, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS preview_events (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL, created REAL NOT NULL
);
"""


def clock():
    return time.time()


def db_path():
    return Path(os.getenv('GPM_REGISTRATION_PREVIEW_DB') or
                str(Path(__file__).resolve().parent.parent / '.registration_preview_private' / 'state.sqlite3'))


def failure(code, message, field=None, status=422, **extra):
    raise HTTPException(status_code=status, detail={
        'code': code, 'message': message, **({'field': field} if field else {}), **extra})


def normalize_phone(raw, country='RU'):
    if country == 'RU':
        from app.phone_numbers import normalize_russian_phone
        try:
            return normalize_russian_phone(raw)
        except ValueError:
            failure('INVALID_PHONE', 'Проверь номер телефона и код страны', 'phone')
    if not isinstance(raw, str) or len(raw) > 64 or re.search(r'[^+0-9()\s.-]', raw):
        failure('INVALID_PHONE', 'Проверь номер телефона и код страны', 'phone')
    value = re.sub(r'[()\s.-]', '', raw)
    if country == 'INT':
        if not re.fullmatch(r'\+[1-9]\d{7,14}', value):
            failure('INVALID_PHONE', 'Укажи международный номер, начиная с +', 'phone')
    else:
        failure('INVALID_PHONE', 'Выбери страну номера', 'phone_country')
    return value


def normalize_name(value, field):
    if not isinstance(value, str): failure('INVALID_NAME', 'Введи имя текстом', field)
    value = unicodedata.normalize('NFC', value.strip())
    if field == 'middle_name' and not value and not MIDDLE_NAME_REQUIRED: return ''  # Unresolved policy: optional in preview only.
    parts = value.split('-')
    if not 1 <= len(value) <= 100 or any(
        not part or not any(unicodedata.category(c).startswith('L') for c in part)
        or any(unicodedata.category(c)[0] not in ('L', 'M') for c in part) for part in parts
    ):
        failure('INVALID_NAME', 'Используй буквы и дефис, без пробелов и цифр', field)
    return value


def validate_answers(changes, previous):
    if not isinstance(changes, dict) or not set(changes).issubset(FIELDS):
        failure('UNKNOWN_FIELD', 'В анкете есть неподдерживаемое поле')
    result = dict(previous)
    for field, value in changes.items():
        if field == 'phone_country':
            if value not in ('RU', 'INT'): failure('INVALID_PHONE', 'Выбери страну номера', field)
            result[field] = value
        elif field == 'phone':
            continue
        elif field in ('first_name', 'last_name', 'middle_name'):
            result[field] = normalize_name(value, field)
        elif field == 'birth_date':
            if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                failure('INVALID_BIRTH_DATE', 'Укажи существующую дату рождения', field)
            try: born = date.fromisoformat(value)
            except ValueError: failure('INVALID_BIRTH_DATE', 'Укажи существующую дату рождения', field)
            today = datetime.fromtimestamp(clock(), ZoneInfo(AGE_TIMEZONE)).date()
            if born > today: failure('INVALID_BIRTH_DATE', 'Дата рождения не может быть в будущем', field)
            age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
            if age < MINIMUM_AGE: failure('AGE_UNDER_18', f'Для регистрации должно исполниться {MINIMUM_AGE} лет', field)
            result[field] = born.isoformat()
        elif field in ('citizenship_ru', 'has_straps', 'has_tools'):
            if type(value) is not bool: failure('INVALID_BOOLEAN', 'Выбери «Да» или «Нет»', field)
            result[field] = value
        elif field in ('city_ids', 'district_ids'):
            kind = 'city' if field == 'city_ids' else 'district'
            valid = {item['id'] for item in LOCATIONS if item['kind'] == kind and item['enabled']}
            if not isinstance(value, list) or len(value) > 50 or any(type(v) is not int or v not in valid for v in value):
                failure('LOCATION_UNAVAILABLE', 'Обнови выбор городов и районов', field)
            result[field] = sorted(set(value))
    if 'phone' in changes or ('phone_country' in changes and result.get('phone')):
        result['phone'] = normalize_phone(changes.get('phone', result.get('phone')), result.get('phone_country', 'RU'))
    if ('city_ids' in changes or 'district_ids' in changes) and not (result.get('city_ids') or result.get('district_ids')):
        failure('NO_LOCATION_SELECTED', 'Выбери хотя бы один город или район', 'city_ids')
    return result


def next_step(answers, verified_phone):
    if not answers.get('phone') or verified_phone != answers['phone']: return 'phone'
    if not (answers.get('city_ids') or answers.get('district_ids')): return 'locations'
    required = ('first_name', 'last_name', 'birth_date', 'citizenship_ru', 'has_straps', 'has_tools')
    if MIDDLE_NAME_REQUIRED: required += ('middle_name',)
    for field in required:
        if field not in answers or answers[field] is None or answers[field] == '': return field
    return 'review'


class PreviewStore:
    @contextmanager
    def connection(self):
        path = db_path()
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        if path.is_symlink() or path.parent.is_symlink(): raise RuntimeError('Unsafe preview storage')
        db = sqlite3.connect(path, timeout=10)
        os.chmod(path, 0o600)
        db.row_factory = sqlite3.Row
        db.executescript(SCHEMA)
        try:
            with db: yield db
        finally: db.close()

    def _row(self, db, session_id, token, *, writable=False):
        if not isinstance(token, str) or not 20 <= len(token) <= 150:
            failure('UNAUTHORIZED', 'Сначала открой свою тестовую анкету', status=401)
        row = db.execute('SELECT * FROM preview_sessions WHERE id=? AND token_hash=?',
                         (session_id, hashlib.sha256(token.encode()).hexdigest())).fetchone()
        if row is None: failure('UNAUTHORIZED', 'Анкета недоступна', status=401)
        if writable and row['expires'] <= clock(): failure('SESSION_EXPIRED', 'Срок черновика истек', status=410)
        return row

    def _revision(self, row, revision):
        if type(revision) is not int or revision != row['revision']:
            failure('REVISION_CONFLICT', 'Анкета изменилась. Обнови ее и проверь ответы заново', status=409)
        if row['profile_id']: failure('ALREADY_COMPLETED', 'Тестовая анкета уже завершена', status=409)

    def _snapshot(self, row):
        answers = json.loads(row['answers'])
        step = next_step(answers, row['verified_phone'])
        status = 'completed' if row['profile_id'] else 'expired' if row['expires'] <= clock() else 'review' if step == 'review' else 'draft'
        return {'preview': True, 'flow_version': FLOW_VERSION, 'registration_id': row['id'],
                'revision': row['revision'], 'answers': answers, 'current_step': step, 'status': status,
                'can_complete': status == 'review', 'phone_verified': bool(answers.get('phone') and row['verified_phone'] == answers['phone']),
                'expires_at': row['expires'], 'profile_id': row['profile_id'], 'profile_active': False,
                'notifications': 'unavailable', 'middle_name_required': MIDDLE_NAME_REQUIRED,
                'minimum_age': MINIMUM_AGE, 'source_channel': 'website',
                'challenge_active': bool(row['challenge_until'] and row['challenge_until'] > clock()),
                'resend_after': max(0, int((row['challenge_sent'] or 0) + 60 - clock()))}

    def create(self):
        token = 'reg_preview_' + secrets.token_urlsafe(32)
        session_id = 'reg_' + uuid4().hex
        now = clock()
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT count(*) FROM preview_sessions').fetchone()[0] >= 5000:
                failure('TEMPORARY_UNAVAILABLE', 'Тестовое хранилище временно недоступно', status=503)
            db.execute('INSERT INTO preview_sessions(id,token_hash,answers,revision,created,updated,expires) VALUES(?,?,?,?,?,?,?)',
                       (session_id, hashlib.sha256(token.encode()).hexdigest(), '{}', 0, now, now, now + TTL))
            row = self._row(db, session_id, token)
            return {**self._snapshot(row), 'session_token': token}

    def read(self, session_id, token):
        with self.connection() as db: return self._snapshot(self._row(db, session_id, token))

    def patch(self, session_id, token, revision, changes):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self._row(db, session_id, token, writable=True)
            self._revision(row, revision)
            answers = validate_answers(changes, json.loads(row['answers']))
            changed_phone = answers.get('phone') != json.loads(row['answers']).get('phone')
            now = clock()
            db.execute('UPDATE preview_sessions SET answers=?,revision=revision+1,updated=?,expires=?,verified_phone=?,challenge_phone=?,challenge_sent=?,challenge_until=?,attempts=? WHERE id=?',
                       (json.dumps(answers, ensure_ascii=False), now, now + TTL,
                        None if changed_phone else row['verified_phone'], None if changed_phone else row['challenge_phone'],
                        None if changed_phone else row['challenge_sent'], None if changed_phone else row['challenge_until'],
                        0 if changed_phone else row['attempts'], session_id))
            return self._snapshot(self._row(db, session_id, token))

    def challenge(self, session_id, token, revision):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self._row(db, session_id, token, writable=True)
            self._revision(row, revision)
            phone = json.loads(row['answers']).get('phone')
            if not phone: failure('INVALID_PHONE', 'Сначала укажи номер телефона', 'phone')
            now = clock()
            if row['challenge_sent'] and now < row['challenge_sent'] + 60:
                failure('RATE_LIMITED', 'Подожди перед повторным кодом', status=429, retry_after=max(1, int(row['challenge_sent'] + 60 - now)))
            db.execute('UPDATE preview_sessions SET revision=revision+1,challenge_phone=?,challenge_sent=?,challenge_until=?,attempts=0,updated=?,expires=? WHERE id=?',
                       (phone, now, now + 300, now, now + TTL, session_id))
            return {**self._snapshot(self._row(db, session_id, token)), 'test_code': TEST_CODE}

    def verify(self, session_id, token, revision, code):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self._row(db, session_id, token, writable=True)
            self._revision(row, revision)
            phone = json.loads(row['answers']).get('phone')
            if not row['challenge_until'] or row['challenge_until'] <= clock() or row['challenge_phone'] != phone:
                failure('CODE_EXPIRED', 'Код устарел. Запроси новый', 'code')
            if row['attempts'] >= 5: failure('RATE_LIMITED', 'Лимит попыток исчерпан. Запроси новый код', 'code', status=429)
            if code != TEST_CODE:
                db.execute('UPDATE preview_sessions SET attempts=attempts+1 WHERE id=?', (session_id,))
                db.commit()
                failure('INVALID_CODE', 'Неверный код. Попробуй еще раз', 'code')
            db.execute('UPDATE preview_sessions SET verified_phone=?,revision=revision+1,updated=?,expires=? WHERE id=?',
                       (phone, clock(), clock() + TTL, session_id))
            return self._snapshot(self._row(db, session_id, token))

    def complete(self, session_id, token, revision, key):
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,128}', key):
            failure('INVALID_IDEMPOTENCY_KEY', 'Повтори подтверждение анкеты', status=400)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self._row(db, session_id, token, writable=True)
            if row['complete_key'] == key and row['complete_revision'] != revision:
                failure('IDEMPOTENCY_CONFLICT', 'Ключ подтверждения относится к другой версии', status=409)
            if row['profile_id']:
                if revision != row['revision']: failure('REVISION_CONFLICT', 'Обнови итоговую карточку', status=409)
                return self._snapshot(row)
            self._revision(row, revision)
            answers = json.loads(row['answers'])
            if next_step(answers, row['verified_phone']) != 'review':
                failure('INCOMPLETE', 'Заполни анкету и подтверди телефон')
            answers = validate_answers(answers, {})  # Recheck age, catalogue and every value.
            profile_id = 'preview_' + uuid4().hex
            try:
                db.execute('INSERT INTO preview_profiles VALUES(?,?,?,?,?)',
                           (profile_id, session_id, answers['phone'], json.dumps(answers, ensure_ascii=False), clock()))
            except sqlite3.IntegrityError:
                failure('PHONE_IN_USE', 'Этот номер уже используется в тестовой анкете. Укажи другой тестовый номер', 'phone', status=409)
            db.execute('INSERT INTO preview_events VALUES(?,?,?,?)', (uuid4().hex, session_id, 'preview.registration.completed', clock()))
            db.execute('UPDATE preview_sessions SET profile_id=?,complete_key=?,complete_revision=? WHERE id=?',
                       (profile_id, key, revision, session_id))
            return self._snapshot(self._row(db, session_id, token))

    def restart(self, session_id, token, revision, confirmed):
        if confirmed is not True: failure('CONFIRMATION_REQUIRED', 'Подтверди начало анкеты заново')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self._row(db, session_id, token, writable=True)
            self._revision(row, revision)
            db.execute('UPDATE preview_sessions SET answers=\'{}\',revision=revision+1,verified_phone=NULL,challenge_phone=NULL,challenge_sent=NULL,challenge_until=NULL,attempts=0,updated=?,expires=? WHERE id=?',
                       (clock(), clock()+TTL, session_id))
            return self._snapshot(self._row(db, session_id, token))


_RATE_LOCK = Lock()
_RATE = {}


def _limit(request, operation):
    key = (request.client.host if request.client else 'unknown', operation)
    now = time.monotonic()
    with _RATE_LOCK:
        for old in list(_RATE):
            if not _RATE[old] or _RATE[old][-1] < now - 1800: del _RATE[old]
        if key not in _RATE and len(_RATE) >= 4000:
            failure('RATE_LIMITED', 'Попробуй позже', status=429)
        history = _RATE.setdefault(key, deque())
        window, maximum = (1800, 15) if operation == 'create' else (60, 120)
        while history and history[0] < now - window: history.popleft()
        if len(history) >= maximum: failure('RATE_LIMITED', 'Слишком много запросов. Попробуй позже', status=429)
        history.append(now)


async def _body(request):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 16384: failure('PAYLOAD_TOO_LARGE', 'Слишком большой запрос', status=413)
    try: value = json.loads(raw)
    except (ValueError, UnicodeError): failure('INVALID_JSON', 'Некорректный запрос', status=400)
    if not isinstance(value, dict): failure('INVALID_JSON', 'Некорректный запрос', status=400)
    return value


def register_routes(app: FastAPI):
    router = app
    store = PreviewStore()

    async def guard(request: Request, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        _limit(request, 'request')

    @router.get(PREFIX + '/locations')
    async def locations(response: Response):
        response.headers['Cache-Control'] = 'no-store'
        return {'preview': True, 'flow_version': FLOW_VERSION, 'locations': LOCATIONS,
                'middle_name_required': MIDDLE_NAME_REQUIRED, 'minimum_age': MINIMUM_AGE}

    @router.post(PREFIX + '/sessions')
    async def create(request: Request, response: Response):
        await guard(request, response)
        _limit(request, 'create')
        return await asyncio.to_thread(store.create)

    @router.get(PREFIX + '/sessions/{session_id}')
    async def read(session_id: str, request: Request, response: Response, authorization: str | None = Header(default=None)):
        await guard(request, response)
        return await asyncio.to_thread(store.read, session_id, (authorization or '').removeprefix('Bearer '))

    @router.api_route(PREFIX + '/sessions/{session_id}/{action}', methods=['POST'])
    async def action(session_id: str, action: str, request: Request, response: Response,
                     authorization: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
        await guard(request, response)
        data = await _body(request)
        allowed = {'expected_revision', 'code'} if action == 'phone-verification' else {'expected_revision', 'confirmed'} if action == 'restart' else {'expected_revision'}
        if set(data) - allowed: failure('UNKNOWN_FIELD', 'Неподдерживаемое поле')
        token = (authorization or '').removeprefix('Bearer ')
        revision = data.get('expected_revision')
        if action == 'phone-challenge': return await asyncio.to_thread(store.challenge, session_id, token, revision)
        if action == 'phone-verification': return await asyncio.to_thread(store.verify, session_id, token, revision, data.get('code'))
        if action == 'complete': return await asyncio.to_thread(store.complete, session_id, token, revision, idempotency_key)
        if action == 'restart': return await asyncio.to_thread(store.restart, session_id, token, revision, data.get('confirmed'))
        failure('NOT_FOUND', 'Действие недоступно', status=404)

    @router.patch(PREFIX + '/sessions/{session_id}')
    async def patch(session_id: str, request: Request, response: Response, authorization: str | None = Header(default=None)):
        await guard(request, response)
        data = await _body(request)
        if set(data) != {'expected_revision', 'answers'}: failure('UNKNOWN_FIELD', 'Неподдерживаемые поля запроса')
        return await asyncio.to_thread(store.patch, session_id, (authorization or '').removeprefix('Bearer '),
                                      data.get('expected_revision'), data['answers'])

