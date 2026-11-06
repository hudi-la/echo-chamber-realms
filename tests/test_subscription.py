import asyncio
import base64
import hashlib
import json
import stat
import time
from types import SimpleNamespace as NS
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from echo.brain import Decision, SubscriptionBrain, make_brain
from echo.config import parse_config
from echo.subscription import (APP_NAME, AUTH_DIR, AuthorizationAttempt, DYNAMIC_CLIENT,
                               ISSUER, PLAN_SCOPE, RESOURCE, SubscriptionError,
                               SubscriptionSession, login, profile_path, read_record,
                               updated_record, validate_identity, write_record)


def tokens(**overrides):
    return {'access_token': 'test-access', 'refresh_token': 'test-refresh',
            'token_type': 'Bearer', 'expires_in': 3600,
            'scope': PLAN_SCOPE + ' resource.invoke offline_access', **overrides}


def record(**overrides):
    return {'client_id': 'test-issued-client', 'subject': 'test-subject',
            'ext_agent_host_id': 'urn:uuid:test-host', 'scopes': [PLAN_SCOPE, 'resource.invoke'],
            'access_token': 'old-test-access', 'refresh_token': 'old-test-refresh',
            'expires_at': 999, **overrides}


def test_pkce_and_new_registration_url():
    attempt = AuthorizationAttempt('urn:uuid:test', 'http://127.0.0.1:1455/auth/callback')
    query = parse_qs(urlsplit(attempt.url()).query)
    expected = base64.urlsafe_b64encode(hashlib.sha256(attempt.verifier.encode()).digest()).decode().rstrip('=')
    assert query['code_challenge'] == [expected]
    assert query['client_id'] == [DYNAMIC_CLIENT]
    assert query['agent_name_hint'] == [APP_NAME]
    assert query['nonce'] == [attempt.nonce]
    assert query['resource'] == [RESOURCE]
    assert PLAN_SCOPE in query['scope'][0]
    form = attempt.exchange_form({'state': attempt.state, 'code': 'test-code', 'client_id': 'test-issued'})
    assert form['client_id'] == 'test-issued'
    assert form['redirect_uri'] == attempt.redirect
    assert form['code_verifier'] == attempt.verifier


@pytest.mark.parametrize('callback', [
    {'state': 'wrong', 'code': 'test-code', 'client_id': 'test-issued'},
    {'code': 'test-code'},
    {'client_id': DYNAMIC_CLIENT, 'code': 'test-code'},
    {'client_id': 'test-issued'},
    {'error': 'access_denied'},
])
def test_invalid_callbacks_are_rejected(callback):
    attempt = AuthorizationAttempt('host', 'http://127.0.0.1:1455/auth/callback')
    callback.setdefault('state', attempt.state)
    with pytest.raises(SubscriptionError):
        attempt.exchange_form(callback)


def test_returning_registration_is_bound_to_client():
    attempt = AuthorizationAttempt('host', 'http://127.0.0.1:1455/auth/callback', 'existing-client')
    query = parse_qs(urlsplit(attempt.url()).query)
    assert query['client_id'] == ['existing-client']
    assert 'agent_name_hint' not in query and 'id_token_hint' not in query
    with pytest.raises(SubscriptionError):
        attempt.exchange_form({'state': attempt.state, 'code': 'test', 'client_id': 'other-client'})
    assert attempt.exchange_form({'state': attempt.state, 'code': 'test'})['client_id'] == 'existing-client'


def test_private_storage_and_profile_isolation(tmp_path):
    a, b = profile_path('a', tmp_path), profile_path('b', tmp_path)
    write_record(a, record())
    write_record(b, record(subject='another-test-subject'))
    assert stat.S_IMODE(a.stat().st_mode) == 0o600
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    assert read_record(a)['subject'] != read_record(b)['subject']
    with pytest.raises(SubscriptionError): profile_path('../escape', tmp_path)
    linked = tmp_path / 'linked.json'
    linked.symlink_to(a)
    with pytest.raises(SubscriptionError): read_record(linked)
    with pytest.raises(SubscriptionError): write_record(linked, {})


@pytest.mark.parametrize('overrides', [
    {'scope': 'openid profile'}, {'refresh_token': ''}, {'access_token': ''},
    {'expires_in': float('nan')}, {'expires_in': -1}, {'token_type': 'Other'},
])
def test_invalid_token_responses_never_replace_credentials(overrides):
    old = record()
    with pytest.raises(SubscriptionError): updated_record(old, tokens(**overrides), now=1000)
    assert old['access_token'] == 'old-test-access'


def test_identity_change_rejected():
    with pytest.raises(SubscriptionError):
        updated_record(record(), tokens(), {'sub': 'other-subject'}, now=1000)


async def test_refresh_is_serialized_across_sessions_and_rotates_atomically(tmp_path):
    path = profile_path('default', tmp_path)
    write_record(path, record())
    requests = []
    async def handle(request):
        requests.append(request)
        await asyncio.sleep(0.01)
        assert 'grant_type=refresh_token' in request.content.decode()
        assert 'old-test-refresh' in request.content.decode()
        return httpx.Response(200, json=tokens())
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        a = SubscriptionSession(directory=tmp_path, http=http, now=lambda: 1000)
        b = SubscriptionSession(directory=tmp_path, http=http, now=lambda: 1000)
        assert await asyncio.gather(a.access_token(), b.access_token()) == ['test-access', 'test-access']
    assert len(requests) == 1
    saved = read_record(path)
    assert saved['refresh_token'] == 'test-refresh' and saved['expires_at'] == 4600


async def test_refresh_failure_keeps_original_record(tmp_path):
    path = profile_path('default', tmp_path)
    original = record()
    write_record(path, original)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(400, json={'error': 'invalid_grant'}))) as http:
        session = SubscriptionSession(directory=tmp_path, http=http, now=lambda: 1000)
        with pytest.raises(SubscriptionError): await session.access_token()
    assert read_record(path) == original


async def test_catalog_and_model_validation_no_silent_model_switch(tmp_path):
    write_record(profile_path('default', tmp_path), record(expires_at=time.time() + 3600))
    def handle(request):
        assert request.headers['authorization'] == 'Bearer old-test-access'
        return httpx.Response(200, json={'models': [
            {'slug': 'gpt-5.5', 'display_name': 'Test model', 'visibility': 'list'},
            {'slug': 'hidden', 'visibility': 'hide'}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        session = SubscriptionSession(directory=tmp_path, http=http)
        assert await session.models() == [{'slug': 'gpt-5.5', 'display_name': 'Test model'}]
        await session.ensure_models(['gpt-5.5'])
        with pytest.raises(SubscriptionError, match='没有配置的模型'):
            await session.ensure_models(['unavailable'])


@pytest.fixture
def signed_identity():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    public.update(kid='test-signing-key', alg='RS256', use='sig')
    def sign(**changes):
        claims = {'iss': ISSUER, 'aud': 'test-issued-client', 'sub': 'test-subject',
                  'exp': time.time() + 300, 'iat': time.time(), 'nonce': 'test-nonce', **changes}
        return jwt.encode(claims, private, algorithm='RS256', headers={'kid': 'test-signing-key'})
    return sign, {'keys': [public]}


async def test_id_token_signature_audience_nonce_and_expiry(signed_identity):
    sign, jwks = signed_identity
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=jwks))) as http:
        claims = await validate_identity(sign(), 'test-issued-client', 'test-nonce', http)
        assert claims['sub'] == 'test-subject'
        for changes in ({'aud': 'wrong'}, {'nonce': 'wrong'}, {'exp': time.time()-10}, {'iss': 'https://wrong.invalid'}):
            with pytest.raises(SubscriptionError):
                await validate_identity(sign(**changes), 'test-issued-client', 'test-nonce', http)
        encoded = sign().split('.')
        encoded[1] = base64.urlsafe_b64encode(json.dumps({'sub': 'forged'}).encode()).decode().rstrip('=')
        with pytest.raises(SubscriptionError):
            await validate_identity('.'.join(encoded), 'test-issued-client', 'test-nonce', http)


async def test_login_loopback_validates_and_persists_without_logging_tokens(tmp_path, monkeypatch, capsys, signed_identity):
    import echo.subscription as module
    sign, jwks = signed_identity
    original_validate = module.validate_identity
    query = {}
    tasks = []
    async def fake_exchange(form, http=None):
        assert form['client_id'] == 'test-issued-client'
        assert form['code_verifier']
        return tokens(id_token=sign(nonce=query['nonce'][0]))
    async def verify(token, client_id, nonce, http=None):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=jwks))) as mock:
            return await original_validate(token, client_id, nonce, mock)
    monkeypatch.setattr(module, 'token_request', fake_exchange)
    monkeypatch.setattr(module, 'validate_identity', verify)
    async def authorize():
        async with httpx.AsyncClient() as http:
            redirect = query['redirect_uri'][0]
            assert urlsplit(redirect).hostname == '127.0.0.1'
            rejected = await http.get(redirect, params={'state': 'wrong', 'code': 'bad'})
            assert rejected.status_code == 400
            accepted = await http.get(redirect, params={'state': query['state'][0], 'code': 'test-code', 'client_id': 'test-issued-client'})
            assert accepted.status_code == 200
    def ready(url):
        query.update(parse_qs(urlsplit(url).query))
        tasks.append(asyncio.create_task(authorize()))
    await login(directory=tmp_path, on_ready=ready, timeout=3)
    await asyncio.gather(*tasks)
    saved = read_record(profile_path('default', tmp_path))
    assert saved['subject'] == 'test-subject' and saved['access_token'] == 'test-access'
    output = capsys.readouterr()
    assert 'test-access' not in output.out and 'test-refresh' not in output.out


class FakeStream:
    def __init__(self, events):
        self.events, self.closed = events, False
    async def __aiter__(self):
        for event in self.events: yield event
    async def close(self): self.closed = True


class Client:
    def __init__(self, stream):
        self.stream, self.calls = stream, []
        self.responses = self
    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.stream
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass


class FakeSession:
    async def access_token(self): return 'fake-subscription-access'


async def test_subscription_brain_stream_shape_and_completed_json():
    stream = FakeStream([NS(type='response.output_text.delta', delta='{"speak":true,'),
                         NS(type='response.output_text.delta', delta='"feeling":"好奇","intent":"问"}'),
                         NS(type='response.completed')])
    client = Client(stream)
    b = SubscriptionBrain('gpt-5.5', session=FakeSession(), client_factory=lambda _: client)
    assert await b.decide('role', 'situation') == Decision(True, feeling='好奇', intent='问')
    call = client.calls[0]
    assert call['stream'] is True and call['store'] is False
    assert call['input'][0]['content'].startswith('situation\n\n')
    assert call['text']['format']['schema']['required'] == ['speak']
    assert call['instructions'] == 'role' and 'max_output_tokens' not in call
    assert call['text']['format']['strict'] is True and stream.closed


@pytest.mark.parametrize('ending', ['response.failed', 'response.incomplete', 'error', None])
async def test_partial_stream_is_never_a_success(ending):
    events = [NS(type='response.output_text.delta', delta='{"speak":true}')]
    if ending: events.append(NS(type=ending))
    stream = FakeStream(events)
    client = Client(stream)
    brain = SubscriptionBrain('gpt-5.5', session=FakeSession(), client_factory=lambda _: client)
    assert not (await brain.decide('s', 'u')).speak
    assert stream.closed and len(client.calls) == 1


async def test_subscription_failure_does_not_create_api_client(capsys):
    class Missing:
        async def access_token(self): raise SubscriptionError('尚未登录订阅。')
    def forbidden(_): raise AssertionError('must not create API client')
    brain = SubscriptionBrain('gpt-5.5', session=Missing(), client_factory=forbidden)
    assert not (await brain.decide('s', 'u')).speak


def test_config_and_factory_route_only_brain_to_subscription(tmp_path, monkeypatch):
    cfg = parse_config('[model]\nprovider="openai"\nauth="subscription"', tmp_path)
    assert cfg.brain_auth == 'subscription' and cfg.mouth == 'off'
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    assert isinstance(make_brain('openai', 'gpt-5.5', 'none', auth='subscription'), SubscriptionBrain)
    with pytest.raises(ValueError): parse_config('[model]\nprovider="anthropic"\nauth="subscription"', tmp_path)
