import http.client
import json
import re
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode
from main import run
from governance.review import submit_review, ReviewError, load_reviews
from governance.audit import verify_chain
from dashboard.app import create_handler

class ReviewFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output=Path(self.temp.name)
        run(self.output,mode='mock')
    def tearDown(self):self.temp.cleanup()
    def test_blocked_case_remains_blocked_after_acknowledge(self):
        x=submit_review(self.output,'INC-003','acknowledge','Investigated simulated subgroup performance issue.')
        self.assertFalse(x['execution_authorized'])
        self.assertEqual(x['gate_decision_unchanged'],'BLOCK_AND_ESCALATE')
        self.assertTrue(verify_chain(self.output/'audit_log.jsonl'))
    def test_refuse_duplicate_review(self):
        submit_review(self.output,'INC-003','reject','Evidence insufficient to permit action.')
        with self.assertRaises(ReviewError): submit_review(self.output,'INC-003','acknowledge','Trying to overwrite previous reviewer.')
    def test_refuse_unknown_case_and_bad_action(self):
        with self.assertRaises(ReviewError): submit_review(self.output,'INC-999','reject','No matching incident number here.')
        with self.assertRaises(ReviewError): submit_review(self.output,'INC-001','execute','Not authorized to perform this action.')
    def test_invalid_chain_prevents_review(self):
        log=self.output/'audit_log.jsonl'
        log.write_text(log.read_text().replace('INC-003','INC-333'),encoding='utf-8')
        with self.assertRaises(ReviewError):submit_review(self.output,'INC-003','reject','Evidence is still insufficient.')
    def test_requires_meaningful_rationale(self):
        with self.assertRaises(ReviewError):submit_review(self.output,'INC-001','reject','no')

class DashboardHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)
        run(self.path,mode='mock')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),create_handler(self.path,'correct-horse-1234'))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3);self.temp.cleanup()
    def req(self, method,path, data=None,cookie=None):
        con=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        headers={}
        if cookie:headers['Cookie']=cookie
        body=None
        if data is not None:
            body=urlencode(data)
            headers['Content-Type']='application/x-www-form-urlencoded'
        con.request(method,path,body,headers)
        res=con.getresponse();b=res.read().decode('utf-8');headers=dict(res.getheaders());code=res.status
        con.close();return code,headers,b
    def login(self):
        code,h,_=self.req('POST','/login',{'password':'correct-horse-1234'})
        self.assertEqual(code,303)
        return h['Set-Cookie'].split(';')[0]
    def test_dashboard_requires_password(self):
        status,_,page=self.req('GET','/')
        self.assertEqual(status,200);self.assertIn('sign-in',page)
        status,_,_=self.req('POST','/login',{'password':'wrong-password'})
        self.assertEqual(status,403)
    def test_dashboard_review_post_rejects_missing_csrf(self):
        cookie=self.login()
        status,_,_=self.req('POST','/review',{'case_id':'INC-003','action':'acknowledge','reason':'Enough detailed evidence for reviewer note.'},cookie)
        self.assertEqual(status,403)
        self.assertEqual(load_reviews(self.path),{})
    def test_review_after_login(self):
        cookie=self.login()
        code,headers,page=self.req('GET','/',cookie=cookie)
        self.assertEqual(code,200)
        match=re.search(r'name="csrf" value="([^"]+)"',page)
        self.assertIsNotNone(match)
        code,_,_=self.req('POST','/review',{'csrf':match.group(1),'case_id':'INC-003','action':'acknowledge','reason':'Confirmed blocked action stays prohibited.'},cookie)
        self.assertEqual(code,303)
        self.assertFalse(load_reviews(self.path)['INC-003']['execution_authorized'])
    def test_login_cookie_httponly(self):
        _,headers,_=self.req('POST','/login',{'password':'correct-horse-1234'})
        self.assertIn('HttpOnly',headers['Set-Cookie'])
        self.assertIn('SameSite=Strict',headers['Set-Cookie'])

if __name__=='__main__':unittest.main()
