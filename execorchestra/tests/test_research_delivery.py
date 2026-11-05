import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import shutil
import uuid

from scripts.research_benchmark import read_delivered_prediction


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        # Use inherited ACLs: mode-0700 temp directories are inaccessible in
        # some managed Windows test environments. Fixtures contain no secrets.
        self.tmp=Path(tempfile.gettempdir())/('research-delivery-'+uuid.uuid4().hex)
        self.tmp.mkdir()
        self.addCleanup(shutil.rmtree,self.tmp)
        self.root=self.tmp/'pipeline'
        self.root.mkdir()

    def delivered(self,name,text='The answer is 42.\n'):
        raw=text.encode('utf-8');(self.root/name).write_bytes(raw)
        value={'delivery_locator':name,'content_sha256':hashlib.sha256(raw).hexdigest(),
               'artifact_descriptor':{'byte_size':len(raw)},
               'publication':{'logical_locator':name,'byte_size':len(raw)}}
        (self.root/'delivery_manifest.json').write_text(json.dumps(value))
        return value

    def test_markdown_delivery_and_stale_txt(self):
        self.delivered('final_output.md','有效答案\n')
        (self.root/'final_output.txt').write_text('stale answer')
        text,evidence=read_delivered_prediction(self.root)
        self.assertEqual(text,'有效答案\n')
        self.assertEqual(evidence['source'],'final_output.md')

    def test_txt_delivery(self):
        self.delivered('final_output.txt')
        self.assertEqual(read_delivered_prediction(self.root)[0],'The answer is 42.\n')

    def test_uncommitted_file_is_not_a_prediction(self):
        (self.root/'final_output.md').write_text('uncommitted')
        self.assertEqual(read_delivered_prediction(self.root),('',{'status':'not_delivered'}))

    def test_corrupted_content_is_rejected(self):
        self.delivered('final_output.md')
        (self.root/'final_output.md').write_text('changed')
        with self.assertRaisesRegex(ValueError,'content_hash_mismatch'):
            read_delivered_prediction(self.root)

    def test_publication_identity_is_checked(self):
        value=self.delivered('final_output.md')
        value['publication']['byte_size']=0
        (self.root/'delivery_manifest.json').write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'descriptor_mismatch'):
            read_delivered_prediction(self.root)

    def test_path_escape_is_rejected(self):
        value=self.delivered('final_output.md')
        value['delivery_locator']='../secret.txt'
        (self.root/'delivery_manifest.json').write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'outside_pipeline'):
            read_delivered_prediction(self.root)


if __name__=='__main__':unittest.main()
