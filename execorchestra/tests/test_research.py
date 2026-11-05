import base64
import json
import unittest
from unittest.mock import patch
from scripts.research_browser import normalize_url, public_host, page_chunk, proxy_options
from scripts.research_benchmark import project_rows, parse_grade


class ResearchTests(unittest.TestCase):
    def test_private_and_invalid_urls(self):
        for value in ['file:///etc/passwd','https://user:pass@example.com','http://example.com:22']:
            with self.assertRaises(ValueError): normalize_url(value)
        self.assertFalse(public_host('localhost'))
        with patch('socket.getaddrinfo',return_value=[(None,None,None,None,('10.0.0.1',80))]):
            self.assertFalse(public_host('public-looking.example'))

    def test_unicode_pagination_is_lossless_and_byte_bounded(self):
        text='资料证据'*8000
        page={'status':'success','page_id':'test','text':text,'links':[{'url':'https://example.com/'+str(i),'text':'资料'*100} for i in range(80)]}
        chunks=[]; offset=0
        while offset is not None:
            part=page_chunk(page,offset)
            self.assertLessEqual(len(json.dumps(part,ensure_ascii=False).encode()),14000)
            chunks.append(part['text']); offset=part['next_text_offset']
        self.assertEqual(''.join(chunks),text)
        links=[]; offset=0
        while offset is not None:
            part=page_chunk(page,0,offset); links+=part['links']; offset=part['next_link_offset']
        self.assertEqual(links,page['links'])
        with self.assertRaises(ValueError): page_chunk(page,len(text)+1)

    def test_proxy_credentials_separated_from_server(self):
        p=proxy_options('http://demo:pass%40word@proxy.example:3128')
        self.assertEqual(p['server'],'http://proxy.example:3128')
        self.assertEqual(p['password'],'pass@word')

    def test_xbench_decryption_and_answer_separation(self):
        key='canary'
        def enc(s): return base64.b64encode(bytes(b^key.encode()[i%len(key)] for i,b in enumerate(s.encode()))).decode()
        tasks,refs=project_rows([{'id':'1','prompt':enc('问题'),'answer':enc('答案'),'canary':key,'reference_steps':'secret'}],'xbench')
        self.assertEqual(tasks[0]['query'],'问题')
        self.assertNotIn('答案',json.dumps(tasks,ensure_ascii=False))
        self.assertNotIn('reference_steps',tasks[0])
        self.assertEqual(refs[0]['reference_answer'],'答案')

    def test_webwalker_golden_path_never_enters_task(self):
        tasks,refs=project_rows([{'question':'When?','answer':'2030','root_url':'https://example.com','info':{'golden_path':['secret']}}],'webwalker')
        self.assertNotIn('secret',json.dumps(tasks))
        with self.assertRaises(ValueError): project_rows([{'question':'x','answer':'y'}],'webwalker')

    def test_invalid_judge_is_error_not_failed_answer(self):
        for text in ['{"correct":"false","reason":"x"}','{"correct":true}', 'not JSON']:
            with self.assertRaises(ValueError): parse_grade(text)
        self.assertTrue(parse_grade('{"correct":true,"reason":"matches"}')['correct'])


if __name__=='__main__': unittest.main()
