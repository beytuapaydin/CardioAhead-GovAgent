"""Local-only, password-protected review UI; no clinical execution paths."""
from __future__ import annotations
import argparse
import hashlib
import hmac
import html
import os
import secrets
import threading
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from governance.audit import verify_chain
from governance.review import ReviewError, load_cases, load_reviews, submit_review

SESSIONS = {}
SESSIONS_LOCK = threading.Lock()
MAX_BODY = 16384

CSS = '''
:root{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;color:#172b35;background:#f4f7f8}
*{box-sizing:border-box}body{margin:0}.wrap{max-width:1050px;margin:0 auto;padding:30px 22px}header{background:#132f3b;color:#fff;padding:24px 0}
h1{font-size:28px;margin:4px 0}.lead{color:#c4dce3}h2{font-size:21px}.panel,.case{background:white;border:1px solid #d8e2e6;border-radius:12px;padding:20px;margin:17px 0;box-shadow:0 2px 8px #173a4a0b}
.case{border-left:5px solid #638393}.blocked{border-left-color:#b46049}.meta{color:#51636b;font-size:14px}.pill{background:#e2f2ef;color:#216455;border-radius:12px;padding:4px 9px;font-size:12px;font-weight:700}.pill.block{background:#f9e7df;color:#a3452e}
button{background:#1a5f70;color:#fff;border:0;padding:10px 16px;border-radius:6px;font-size:14px;cursor:pointer}button:hover{background:#164a59}input,textarea{font:inherit;padding:10px;border:1px solid #bdcdd2;border-radius:6px;width:100%;margin:8px 0}textarea{min-height:70px}.actions{display:flex;gap:10px;flex-wrap:wrap}.actions button{background:#345e70}.actions button[value=reject]{background:#984934}form{margin-top:15px}.warn{padding:13px 16px;border-radius:8px;background:#fff1db;color:#714b15}.danger{background:#fce5e3;color:#8b2929}.ok{background:#e7f5ef;color:#226247}.foot{color:#596d76;font-size:13px}.small{font-size:13px}
'''

def e(s):
    return html.escape(str(s), quote=True)

def layout(content, logged_in=False):
    nav = '<form action="/logout" method="post"><button>Log out</button></form>' if logged_in else ''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CardioAhead GovAgent Review</title><style>{CSS}</style></head><body><header><div class="wrap"><div class="small">CARDIOAHEAD / GOVAGENT v0.4 · SYNTHETIC DEMO</div><h1>Human Review Dashboard</h1><div class="lead">Authority is separate from intelligence. Clinical actions are never executed.</div>{nav}</div></header><main class="wrap">{content}<p class="foot">Educational prototype only. No patient data, no real medical decisions, no regulatory approvals, no external tool execution.</p></main></body></html>'''


def create_handler(output_dir: Path, password: str, auditor_password: str | None = None):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body, status=200, cookie=None):
            data = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Referrer-Policy', 'no-referrer')
            if cookie: self.send_header('Set-Cookie', cookie)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def _form(self):
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0 or length > MAX_BODY:
                raise ReviewError('Invalid request size')
            form = parse_qs(self.rfile.read(length).decode('utf-8'), keep_blank_values=True)
            return {k: v[0] for k,v in form.items()}
        def _session(self):
            cookies = SimpleCookie()
            try: cookies.load(self.headers.get('Cookie', ''))
            except Exception: return None
            token = cookies.get('govsession')
            if token is None: return None
            with SESSIONS_LOCK: return SESSIONS.get(token.value)
        def _csrf_ok(self, form, session):
            return bool(session and hmac.compare_digest(form.get('csrf',''),session['csrf']))
        def _origin_ok(self):
            origin = self.headers.get('Origin')
            if not origin: return True
            return origin in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}')
        def do_GET(self):
            route = urlsplit(self.path).path
            if route == '/login' or not self._session():
                self._send(layout('<section class="panel"><h2>Reviewer sign-in</h2><form method="post" action="/login"><label>Local reviewer password<input type="password" name="password" required autocomplete="current-password"></label><button>Sign in</button></form><p class="foot">Password is set in GOVAGENT_REVIEW_PASSWORD or printed at startup.</p></section>'))
                return
            if route != '/':
                self._send(layout('<p>Page not found</p>', True), 404);return
            session = self._session()
            role = session.get('role', 'reviewer')
            valid = verify_chain(output_dir/'audit_log.jsonl') and (output_dir/'audit_log.jsonl').exists()
            try:
                cases = load_cases(output_dir); reviews = load_reviews(output_dir)
            except (ReviewError, OSError, ValueError) as ex:
                self._send(layout(f'<div class="warn danger">{e(ex)}</div>', True), 500);return
            cards=[]
            for row in cases:
                item,gate=row['incident'],row['gate']
                id_=str(item['id']);blocked=gate.get('human_review_required',True)
                state=reviews.get(id_)
                badge=f'<span class="pill {"block" if blocked else ""}">{e(gate["decision"])}</span>'
                if state:
                    review=f'<p class="warn ok">Reviewed: {e(state["review_status"])} by {e(state["reviewer"])} — {e(state["rationale"])}. No execution authorized.</p>'
                elif role == 'auditor':
                    review='<p class="foot">Read-only auditor: reviews cannot be submitted.</p>'
                else:
                    review=f'''<form method="post" action="/review"><input type="hidden" name="csrf" value="{e(session['csrf'])}"><input type="hidden" name="case_id" value="{e(id_)}"><label>Review rationale (10–1000 characters)<textarea name="reason" maxlength="1000" required placeholder="Evidence considered, limitations, next steps..." ></textarea></label><div class="actions"><button name="action" value="acknowledge">Acknowledge review only</button><button name="action" value="request_changes">Request changes</button><button name="action" value="reject">Reject</button></div></form>'''
                cards.append(f'''<article class="case {'blocked' if blocked else ''}"><div>{badge} <strong>{e(id_)}</strong></div><h2>{e(item.get('description','No description'))}</h2><p class="meta"><b>Requested:</b> {e(item.get('proposed_action'))} · <b>Illustrative IEC class:</b> {e(item.get('illustrative_iec62304_class'))} · <b>Uncertainty:</b> {e(item.get('uncertainty'))}</p><p><b>Evidence:</b> {e(item.get('evidence_note','Missing'))}</p><p><b>Gate reasons:</b> {e(', '.join(gate.get('reasons',[])) or 'Routine documentation only')}</p><p class="meta">Clinical or regulatory execution is disabled regardless of review outcome.</p>{review}</article>''')
            banner=('<div class="warn ok">Audit hash chain verified. Local changes may still be rehashed by an attacker with filesystem access.</div>' if valid else '<div class="warn danger">Audit integrity could not be verified. Reviews are disabled.</div>')
            self._send(layout(banner+'<div class="panel">Role: '+e(role)+' · <b>'+str(len(cases))+'</b> synthetic cases · <b>'+str(sum(1 for x in cases if x['gate'].get('human_review_required')))+'</b> blocked/escalated · <b>'+str(len(reviews))+'</b> reviewed</div>'+''.join(cards), True))
        def do_POST(self):
            route = urlsplit(self.path).path
            if not self._origin_ok():
                request_origin = self.headers.get('Origin', '(missing)')
                expected_origin = f'http://127.0.0.1:{self.server.server_port}'
                print(f'[LOCAL DEBUG] Rejected POST Origin: {request_origin!r}; expected {expected_origin!r} or localhost equivalent', flush=True)
                self._send(layout(
                    '<div class="warn danger"><strong>Origin mismatch</strong>'
                    '<p>Request origin: <code>' + e(request_origin) + '</code></p>'
                    '<p>Expected origin: <code>' + e(expected_origin) + '</code> or localhost equivalent.</p>'
                    '<p>This request was blocked. No password was checked. Please check browser URL or extensions.</p>'
                    '</div>'), 403)
                return
            try: form=self._form()
            except (ReviewError,ValueError,UnicodeDecodeError) as ex:
                self._send(layout(f'<p>{e(ex)}</p>'),400);return
            if route=='/login':
                supplied = form.get('password','')
                hash_given = hashlib.sha256(supplied.encode()).digest()
                is_reviewer = hmac.compare_digest(hash_given, hashlib.sha256(password.encode()).digest())
                is_auditor = bool(auditor_password and hmac.compare_digest(hash_given, hashlib.sha256(auditor_password.encode()).digest()))
                if not (is_reviewer or is_auditor):
                    self._send(layout('<div class="warn danger">Invalid password</div>'),403);return
                tok,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(24)
                with SESSIONS_LOCK: SESSIONS[tok]={'csrf':csrf, 'role':'reviewer' if is_reviewer else 'auditor'}
                self.send_response(303);self.send_header('Location','/')
                self.send_header('Set-Cookie',f'govsession={tok}; HttpOnly; SameSite=Strict; Path=/')
                self.send_header('Content-Length','0');self.end_headers();return
            session=self._session()
            if not session:
                self._send(layout('<p>Authentication required</p>'),401);return
            if route=='/logout':
                cookies=SimpleCookie();cookies.load(self.headers.get('Cookie',''))
                if 'govsession' in cookies:
                    with SESSIONS_LOCK: SESSIONS.pop(cookies['govsession'].value,None)
                self.send_response(303);self.send_header('Location','/login')
                self.send_header('Set-Cookie','govsession=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/')
                self.send_header('Content-Length','0');self.end_headers();return
            if route!='/review': self._send(layout('<p>Not found</p>',True),404);return
            if session.get('role') != 'reviewer':
                self._send(layout('<p>Read-only role cannot submit reviews</p>',True),403);return
            if not self._csrf_ok(form,session):
                self._send(layout('<p>Invalid form token</p>',True),403);return
            try:
                submit_review(output_dir,form.get('case_id',''),form.get('action',''),form.get('reason',''))
            except (ReviewError,ValueError,OSError) as ex:
                self._send(layout(f'<div class="warn danger">Review not saved: {e(ex)}</div><p><a href="/">Back to dashboard</a></p>',True),400);return
            self.send_response(303);self.send_header('Location','/')
            self.send_header('Content-Length','0');self.end_headers()
        def log_message(self,format,*args):
            pass
    return Handler


def serve(output_dir:Path,port:int=8765,password:str|None=None,auditor_password:str|None=None):
    password = password or os.environ.get('GOVAGENT_REVIEW_PASSWORD')
    if not password:
        password = secrets.token_urlsafe(18)
        print('Temporary reviewer password:',password,flush=True)
    if len(password)<12:
        raise ValueError('Reviewer password must be at least 12 characters')
    auditor_password = auditor_password or os.environ.get('GOVAGENT_AUDITOR_PASSWORD')
    if auditor_password and (len(auditor_password) < 12 or auditor_password == password):
        raise ValueError('Auditor password must be distinct and at least 12 characters')
    server=ThreadingHTTPServer(('127.0.0.1',port),create_handler(output_dir,password,auditor_password))
    print(f'Local dashboard: http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    finally:server.server_close()

if __name__=='__main__':
    from main import ROOT
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'output'/'demo')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    serve(args.output,args.port)
