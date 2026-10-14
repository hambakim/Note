"""카카오톡 '나에게 보내기'로 메시지를 보낸다.

카카오 API는 OAuth 방식이라 토큰이 두 종류다.
- access_token : 실제로 메시지를 보낼 때 쓰는 열쇠. 몇 시간이면 만료된다.
- refresh_token: access_token을 새로 받는 열쇠. 약 2개월 유효하고,
                 만료 1개월 전부터는 갱신할 때 새 refresh_token이 같이 내려온다.

설정 값은 환경변수(GitHub Actions) 또는 kakao_token.json(내 PC)에서 읽는다.
  KAKAO_REST_API_KEY   : 카카오 개발자 콘솔의 REST API 키 (필수)
  KAKAO_CLIENT_SECRET  : 클라이언트 시크릿을 켰다면 그 값 (선택)
  KAKAO_REFRESH_TOKEN  : 처음 로그인할 때 받은 refresh_token (필수)
  KAKAO_REDIRECT_URI   : 로그인할 때 쓸 Redirect URI (기본 https://localhost)
"""

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
TEXT_LIMIT = 200  # 텍스트 템플릿 한 건의 최대 글자 수
DEFAULT_REDIRECT_URI = "https://localhost"
TOKEN_FILE = Path(__file__).resolve().parent.parent / "kakao_token.json"


class KakaoError(Exception):
    pass


def http_post(url, data, headers=None):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers or {}, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded;charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise KakaoError(f"카카오 API 오류 {e.code}: {detail}") from e


def _mask(value):
    """GitHub Actions 로그에 토큰이 찍히지 않도록 가린다."""
    if value and os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::add-mask::{value}")


class KakaoClient:
    def __init__(self, token_file=TOKEN_FILE, post=http_post):
        self.token_file = Path(token_file)
        self.post = post
        saved = self._load_file()
        env = os.environ
        self.rest_key = env.get("KAKAO_REST_API_KEY") or saved.get("rest_api_key")
        self.client_secret = env.get("KAKAO_CLIENT_SECRET") or saved.get("client_secret")
        self.redirect_uri = env.get("KAKAO_REDIRECT_URI") or saved.get("redirect_uri") or DEFAULT_REDIRECT_URI
        self.refresh_token = env.get("KAKAO_REFRESH_TOKEN") or saved.get("refresh_token")
        self.access_token = saved.get("access_token")
        self.expires_at = saved.get("expires_at", 0)
        self.new_refresh_token = None  # 이번 실행 중 새로 발급된 refresh_token
        _mask(self.refresh_token)
        _mask(self.client_secret)

    # ---------- 토큰 파일 (내 PC용) ----------

    def _load_file(self):
        if self.token_file.exists():
            return json.loads(self.token_file.read_text(encoding="utf-8"))
        return {}

    def _save_file(self):
        if os.environ.get("GITHUB_ACTIONS") == "true":
            return  # Actions에서는 파일로 남기지 않는다 (저장소에 올라가면 안 됨)
        data = {
            "rest_api_key": self.rest_key,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "refresh_token": self.refresh_token,
            "access_token": self.access_token,
            "expires_at": self.expires_at,
        }
        self.token_file.write_text(json.dumps(data, indent=1), encoding="utf-8")

    # ---------- 로그인 ----------

    def authorize_url(self):
        self._require_key()
        q = urllib.parse.urlencode({
            "client_id": self.rest_key,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "talk_message",
        })
        return f"{AUTH_URL}?{q}"

    def login(self, code_or_url):
        """로그인 후 주소창에 뜬 주소(또는 code 값)로 토큰을 받아 저장한다."""
        self._require_key()
        code = code_or_url.strip()
        if code.startswith("http"):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(code).query)
            if "error" in query:
                raise KakaoError(f"로그인 거부/실패: {query.get('error_description', query['error'])}")
            code = query.get("code", [""])[0]
        if not code:
            raise KakaoError("주소에서 code 값을 찾지 못했습니다.")
        data = {
            "grant_type": "authorization_code",
            "client_id": self.rest_key,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret
        self._apply_token(self.post(TOKEN_URL, data))
        self._save_file()
        return self.refresh_token

    # ---------- 토큰 갱신 ----------

    def _require_key(self):
        if not self.rest_key:
            raise KakaoError("KAKAO_REST_API_KEY가 없습니다. README의 카카오 설정을 먼저 하세요.")

    def _apply_token(self, res):
        if "access_token" not in res:
            raise KakaoError(f"토큰 응답에 access_token이 없습니다: {res}")
        self.access_token = res["access_token"]
        _mask(self.access_token)
        self.expires_at = time.time() + int(res.get("expires_in", 0)) - 60
        if res.get("refresh_token"):
            if self.refresh_token and res["refresh_token"] != self.refresh_token:
                self.new_refresh_token = res["refresh_token"]
            self.refresh_token = res["refresh_token"]
            _mask(self.refresh_token)

    def ensure_access_token(self):
        if self.access_token and time.time() < self.expires_at:
            return self.access_token
        self._require_key()
        if not self.refresh_token:
            raise KakaoError("refresh_token이 없습니다. `python -m lotto_analyzer kakao login`으로 먼저 로그인하세요.")
        data = {"grant_type": "refresh_token", "client_id": self.rest_key,
                "refresh_token": self.refresh_token}
        if self.client_secret:
            data["client_secret"] = self.client_secret
        self._apply_token(self.post(TOKEN_URL, data))
        self._save_file()
        return self.access_token

    # ---------- 메시지 보내기 ----------

    def send_text(self, text, link="https://www.dhlottery.co.kr", button="동행복권 열기"):
        token = self.ensure_access_token()
        template = {
            "object_type": "text",
            "text": text,
            "link": {"web_url": link, "mobile_web_url": link},
            "button_title": button,
        }
        res = self.post(MEMO_URL, {"template_object": json.dumps(template, ensure_ascii=False)},
                        headers={"Authorization": f"Bearer {token}"})
        if res.get("result_code") != 0:
            raise KakaoError(f"메시지 전송 실패: {res}")
        return res

    def send_long_text(self, text, **kw):
        """200자를 넘으면 줄 단위로 나눠 여러 건으로 보낸다."""
        chunks = split_text(text)
        for c in chunks:
            self.send_text(c, **kw)
        return len(chunks)


def split_text(text, limit=TEXT_LIMIT):
    chunks, cur = [], ""
    for line in text.split("\n"):
        if len(line) > limit:
            raise KakaoError(f"한 줄이 {limit}자를 넘습니다: {line[:30]}...")
        candidate = f"{cur}\n{line}" if cur else line
        if len(candidate) > limit:
            chunks.append(cur)
            cur = line
        else:
            cur = candidate
    if cur:
        chunks.append(cur)
    return chunks
