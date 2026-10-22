"""ChatGPT plan authorization for the brain only; credentials never enter the repo.

python -m echo.subscription login | status | models | logout [--profile NAME]
Official SIWC public-client OAuth + PKCE, with an HTTP loopback callback.
"""
import argparse
import asyncio
import base64
from contextlib import asynccontextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import tempfile
import time
from urllib.parse import urlencode
import uuid
import webbrowser

import httpx

ISSUER = 'https://auth.openai.com'
AUTHORIZE = ISSUER + '/api/accounts/authorize'
TOKEN = ISSUER + '/api/accounts/oauth/token'
REVOKE = ISSUER + '/api/accounts/oauth/revoke'
JWKS = ISSUER + '/.well-known/jwks.json'
RESOURCE = 'https://api.openai.com/v1'
PLAN_SCOPE = 'chatgpt.tokens.use.direct'
SCOPES = 'openid profile email offline_access resource.invoke ' + PLAN_SCOPE
DYNAMIC_CLIENT = 'dynamic_agent_client'
APP_NAME = 'Echo Chamber Realms'
AUTH_DIR = Path.home() / '.config' / 'echo-chamber' / 'subscription'


class SubscriptionError(RuntimeError):
    """Only app-authored safe messages; never attach raw OAuth/API responses."""


def profile_path(profile: str, directory: Path = AUTH_DIR) -> Path:
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', profile):
        raise SubscriptionError('账户标签只能包含字母、数字、下划线或短横线。')
    return directory / f'{profile}.json'


def read_record(path: Path) -> dict:
    if path.is_symlink():
        raise SubscriptionError('授权文件不能是符号链接。')
    if not path.exists():
        return {}
    if path.stat().st_uid != os.getuid():
        raise SubscriptionError('授权文件不属于当前用户。')
    path.chmod(0o600)
    try:
        data = json.loads(path.read_text())
    except (ValueError, OSError):
        raise SubscriptionError('授权记录无法读取；请重新登录。') from None
    if not isinstance(data, dict):
        raise SubscriptionError('授权记录格式无效。')
    return data


def write_record(path: Path, data: dict) -> None:
    if path.parent.is_symlink() or path.is_symlink():
        raise SubscriptionError('授权目录或文件不能是符号链接。')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.auth-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@asynccontextmanager
async def credential_lock(path: Path):
    """Serialize rotating refresh tokens across roles AND processes."""
    if path.parent.is_symlink() or path.is_symlink():
        raise SubscriptionError('授权目录或文件不能是符号链接。')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path.with_suffix('.lock'), flags, 0o600)
    acquired = False
    try:
        deadline = time.monotonic() + 30
        while not acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SubscriptionError('另一个进程正在更新授权，请稍后重试。')
                await asyncio.sleep(0.05)
        yield
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def host_id(directory: Path) -> str:
    path = directory / 'host.json'
    data = read_record(path)
    if not data.get('ext_agent_host_id'):
        data = {'ext_agent_host_id': 'urn:uuid:' + str(uuid.uuid4())}
        write_record(path, data)
    return data['ext_agent_host_id']


class AuthorizationAttempt:
    def __init__(self, host: str, redirect: str, client_id: str | None = None):
        self.client_id = client_id
        self.state = secrets.token_urlsafe(32)
        self.nonce = secrets.token_urlsafe(32)
        self.verifier = secrets.token_urlsafe(64)
        self.redirect = redirect
        self.host = host

    def url(self) -> str:
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).decode().rstrip('=')
        params = dict(client_id=self.client_id or DYNAMIC_CLIENT,
                      ext_agent_host_id=self.host, response_type='code', redirect_uri=self.redirect,
                      scope=SCOPES, resource=RESOURCE, state=self.state, nonce=self.nonce,
                      code_challenge_method='S256', code_challenge=challenge)
        if self.client_id is None:
            params['agent_name_hint'] = APP_NAME
        # No id_token_hint in URLs/logs; returning users select their account in the browser.
        return AUTHORIZE + '?' + urlencode(params)

    def exchange_form(self, callback: dict) -> dict:
        if not secrets.compare_digest(str(callback.get('state', '')), self.state):
            raise SubscriptionError('OAuth state 校验失败。')
        if callback.get('error'):
            raise SubscriptionError('用户未完成订阅授权。')
        issued = callback.get('client_id') or self.client_id
        if not issued or issued == DYNAMIC_CLIENT or (self.client_id and issued != self.client_id):
            raise SubscriptionError('OAuth client_id 校验失败。')
        if not callback.get('code'):
            raise SubscriptionError('OAuth 回调缺少授权码。')
        return dict(grant_type='authorization_code', client_id=issued, code=callback['code'],
                    code_verifier=self.verifier, redirect_uri=self.redirect, resource=RESOURCE)


async def token_request(form: dict, http=None) -> dict:
    if http is None:
        async with httpx.AsyncClient(timeout=20) as client:
            return await token_request(form, client)
    try:
        response = await http.post(TOKEN, data=form)
        if response.status_code != 200:
            raise SubscriptionError(f'订阅授权更新失败（HTTP {response.status_code}），请重新登录。')
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise SubscriptionError('订阅授权服务暂不可用；请稍后重试。') from None


async def validate_identity(token: str, client_id: str, nonce: str | None, http=None) -> dict:
    import jwt
    if http is None:
        async with httpx.AsyncClient(timeout=20) as client:
            return await validate_identity(token, client_id, nonce, client)
    try:
        response = await http.get(JWKS)
        response.raise_for_status()
        keys = jwt.PyJWKSet.from_dict(response.json()).keys
        header = jwt.get_unverified_header(token)
        if header.get('alg') != 'RS256':
            raise ValueError('algorithm')
        key = next(k.key for k in keys if k.key_id == header.get('kid'))
        claims = jwt.decode(token, key, algorithms=['RS256'], audience=client_id, issuer=ISSUER,
                            options={'require': ['exp', 'iat', 'iss', 'aud', 'sub']})
        if nonce is not None and not secrets.compare_digest(str(claims.get('nonce', '')), nonce):
            raise ValueError('nonce')
        return claims
    except (jwt.PyJWTError, httpx.HTTPError, ValueError, StopIteration, KeyError):
        raise SubscriptionError('订阅登录身份校验失败。') from None


def updated_record(old: dict, tokens: dict, identity: dict | None = None, now=None) -> dict:
    """Validate completely before atomically replacing any rotating credentials."""
    now = time.time() if now is None else now
    scopes = tokens.get('scope', ' '.join(old.get('scopes', []))).split()
    if PLAN_SCOPE not in scopes or 'resource.invoke' not in scopes:
        raise SubscriptionError('该账户未授予 ChatGPT 订阅用量权限。')
    if tokens.get('token_type', '').lower() != 'bearer':
        raise SubscriptionError('订阅授权返回了不支持的 token 类型。')
    if not all(isinstance(tokens.get(k), str) and tokens[k] for k in ('access_token', 'refresh_token')):
        raise SubscriptionError('订阅授权缺少访问或刷新凭据。')
    try:
        lifetime = float(tokens['expires_in'])
    except (KeyError, TypeError, ValueError):
        raise SubscriptionError('订阅授权缺少有效的过期时间。') from None
    if not math.isfinite(lifetime) or lifetime <= 0:
        raise SubscriptionError('订阅授权过期时间无效。')
    if identity is not None and old.get('subject') and identity['sub'] != old['subject']:
        raise SubscriptionError('登录账户与所选记录不一致；请使用不同的 --profile 标签。')
    result = {**old, 'access_token': tokens['access_token'], 'refresh_token': tokens['refresh_token'],
              'scopes': scopes, 'token_type': 'Bearer', 'expires_at': now + lifetime,
              'saved_at': now}
    if tokens.get('id_token'):
        result['id_token'] = tokens['id_token']
    if identity is not None:
        result.update(subject=identity['sub'], issuer=ISSUER, email=identity.get('email', ''))
    result['earliest_refresh_at'] = tokens.get('earliest_refresh_at', 0)
    return result


class SubscriptionSession:
    def __init__(self, profile='default', directory: Path = AUTH_DIR, http=None, now=time.time):
        self.path = profile_path(profile, directory)
        self.http, self.now = http, now
        self._lock = asyncio.Lock()

    async def access_token(self) -> str:
        async with self._lock, credential_lock(self.path):
            record = read_record(self.path)
            if not record.get('access_token') or not record.get('client_id'):
                raise SubscriptionError('脑子尚未登录订阅。先运行 python -m echo.subscription login。')
            if PLAN_SCOPE not in record.get('scopes', []):
                raise SubscriptionError('订阅用量授权未开启，请重新登录。')
            remaining = record.get('expires_at', 0) - self.now()
            earliest = record.get('earliest_refresh_at', 0)
            if remaining > 60 or (remaining > 0 and isinstance(earliest, (int, float)) and self.now() < earliest):
                return record['access_token']
            if not record.get('refresh_token'):
                raise SubscriptionError('订阅缺少刷新凭据，请重新登录。')
            tokens = await token_request(dict(grant_type='refresh_token', client_id=record['client_id'],
                                              refresh_token=record['refresh_token'], resource=RESOURCE), self.http)
            identity = None
            if tokens.get('id_token'):
                identity = await validate_identity(tokens['id_token'], record['client_id'], None, self.http)
            record = updated_record(record, tokens, identity, self.now())
            write_record(self.path, record)
            return record['access_token']

    async def models(self) -> list[dict]:
        token = await self.access_token()
        async def get(http):
            try:
                response = await http.get(RESOURCE + '/models', headers={'Authorization': 'Bearer ' + token})
                if response.status_code != 200:
                    raise SubscriptionError(f'订阅模型目录不可用（HTTP {response.status_code}）。')
                data = response.json()
                return [{'slug': m['slug'], 'display_name': m.get('display_name', m['slug'])}
                        for m in data.get('models', []) if m.get('visibility') == 'list' and m.get('slug')]
            except (httpx.HTTPError, ValueError):
                raise SubscriptionError('订阅模型目录暂时无法读取。') from None
        if self.http is not None:
            return await get(self.http)
        async with httpx.AsyncClient(timeout=20) as http:
            return await get(http)

    async def ensure_models(self, names):
        models = await self.models()
        available = {m['slug'] for m in models}
        missing = set(names) - available
        if missing:
            raise SubscriptionError('订阅账户没有配置的模型：' + ', '.join(sorted(missing))
                                    + '。运行 python -m echo.subscription models 查看；不会自动换模型或改走收费 API。')


async def login(profile='default', directory: Path = AUTH_DIR, opener=webbrowser.open,
                on_ready=None, timeout=300):
    from aiohttp import web
    path = profile_path(profile, directory)
    async with credential_lock(path):
        old = read_record(path)
        future = asyncio.get_running_loop().create_future()
        attempt = None
        async def callback(request):
            if not secrets.compare_digest(request.query.get('state', ''), attempt.state):
                return web.Response(status=400, text='Invalid authorization state.')
            if future.done():
                return web.Response(status=409, text='Authorization already received.')
            future.set_result(dict(request.query))
            return web.Response(text='Authorization received. Return to Echo Chamber Realms.')
        app = web.Application()
        app.router.add_get('/auth/callback', callback)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        try:
            await web.TCPSite(runner, '127.0.0.1', 0).start()
            redirect = f'http://127.0.0.1:{runner.addresses[0][1]}/auth/callback'
            attempt = AuthorizationAttempt(host_id(directory), redirect, old.get('client_id'))
            url = attempt.url()
            if on_ready:
                on_ready(url)
            else:
                print('Continue with ChatGPT：请在浏览器完成 ECR 的登录和订阅用量授权。')
                if not opener(url):
                    raise SubscriptionError('无法打开浏览器；请在本机终端重试登录。')
            returned = await asyncio.wait_for(future, timeout)
            form = attempt.exchange_form(returned)
            tokens = await token_request(form)
            if not tokens.get('id_token'):
                raise SubscriptionError('授权服务未返回可验证的身份。')
            identity = await validate_identity(tokens['id_token'], form['client_id'], attempt.nonce)
            record = updated_record({**old, 'client_id': form['client_id'],
                                     'ext_agent_host_id': attempt.host}, tokens, identity)
            write_record(path, record)
            print('订阅授权已保存。凭据仅保存在用户配置目录。')
        except asyncio.TimeoutError:
            raise SubscriptionError('等待浏览器授权超时，请重新运行登录。') from None
        finally:
            await runner.cleanup()


async def logout(profile='default', directory: Path = AUTH_DIR):
    path = profile_path(profile, directory)
    async with credential_lock(path):
        record = read_record(path)
        revoked = not bool(record.get('refresh_token'))
        if not revoked:
            try:
                async with httpx.AsyncClient(timeout=20) as http:
                    response = await http.post(REVOKE, data=dict(token=record['refresh_token'],
                        token_type_hint='refresh_token', client_id=record['client_id']))
                    revoked = response.status_code == 200
            except httpx.HTTPError:
                pass
        for key in ('access_token', 'refresh_token', 'id_token', 'expires_at', 'scopes'):
            record.pop(key, None)
        if record:
            write_record(path, record)
        print('已退出订阅登录。' if revoked else '已清除本地凭据；远程撤销未确认，请在 ChatGPT 设置中断开 ECR。')


async def command(args):
    path = profile_path(args.profile)
    if args.action == 'login':
        await login(args.profile)
    elif args.action == 'logout':
        await logout(args.profile)
    elif args.action == 'models':
        for model in await SubscriptionSession(args.profile).models():
            print(f"{model['slug']}  {model['display_name']}")
    else:
        record = read_record(path)
        print(f'账户标签：{args.profile}；已登录：{bool(record.get("access_token"))}；'
              f'订阅授权：{PLAN_SCOPE in record.get("scopes", [])}；'
              f'访问凭据未过期：{record.get("expires_at", 0) > time.time()}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('login', 'status', 'models', 'logout'))
    parser.add_argument('--profile', default='default', help='独立账户记录标签；不同账户请用不同标签')
    args = parser.parse_args()
    try:
        asyncio.run(command(args))
    except SubscriptionError as error:
        raise SystemExit(str(error)) from None
    except Exception as error:
        # OAuth responses/URLs can contain credentials. Never print the raw exception.
        raise SystemExit(f'订阅授权操作失败（{type(error).__name__}）；请稍后重试。') from None


if __name__ == '__main__':
    main()
