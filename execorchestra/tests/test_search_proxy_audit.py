import json
import unittest
from scripts.search_proxy_audit import proxy_state


class ProxyAuditTests(unittest.TestCase):
    def test_reports_matches_without_exporting_credentials(self):
        secret='http://example-user:private-password@proxy.example:3128'
        env={name:secret for name in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']}
        env['NO_PROXY']='localhost,127.0.0.1,::1'
        result=proxy_state(env,secret)
        self.assertTrue(result['loopback_bypass'])
        self.assertTrue(all(x['matches_expected'] for x in result['variables'].values()))
        for text in ['private-password','example-user','proxy.example']:
            self.assertNotIn(text,json.dumps(result))

    def test_missing_or_different_proxy_is_not_a_match(self):
        result=proxy_state({'HTTPS_PROXY':'http://wrong-proxy'},'http://right-proxy')
        self.assertFalse(result['variables']['HTTPS_PROXY']['matches_expected'])
        self.assertFalse(result['variables']['HTTP_PROXY']['present'])
        self.assertFalse(proxy_state({},None)['variables']['HTTP_PROXY']['matches_expected'])


if __name__=='__main__':unittest.main()
