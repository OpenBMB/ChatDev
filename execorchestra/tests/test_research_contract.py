"""Check the browser adapter against the unchanged production output gate."""
import unittest
from scripts.prepare_research_profile import browser_output_schema
from scripts.research_browser import page_chunk
from sgar_mvp.src.model_response_contracts import validate_json_schema_instance
from sgar_mvp.src.native_output_contracts import require_native_json_schema


class BrowserContractTests(unittest.TestCase):
    def test_native_output_and_continuation_satisfy_runtime_contract(self):
        declared=browser_output_schema()
        schema=require_native_json_schema({'artifact_type':'json','json_schema':declared},declared)
        page={'status':'success','tool':'browser_read_page','requested_url':'https://example.com/',
              'final_url':'https://example.com/','title':'Example','http_status':200,
              'fetched_at':'2026-10-30T00:00:00+00:00','page_id':'test','rendered':True,
              'content_truncated':False,'links_truncated':False,
              'text':'source evidence '*1000,'links':[{'url':'https://example.com/next','text':'Next'}]}
        first=page_chunk(page)
        valid,reason=validate_json_schema_instance(first,schema)
        self.assertTrue(valid,reason)
        self.assertIsNotNone(first['next_text_offset'])
        second=page_chunk(page,first['next_text_offset'])
        valid,reason=validate_json_schema_instance(second,schema)
        self.assertTrue(valid,reason)
        self.assertEqual(second['page_id'],first['page_id'])
        second['links']=[{'url':17,'text':'invalid link'}]
        self.assertFalse(validate_json_schema_instance(second,schema)[0])


if __name__=='__main__':unittest.main()
