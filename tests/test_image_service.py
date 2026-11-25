import asyncio
import base64
import unittest
from unittest.mock import patch

import httpx
import image_service as service


class ImageServiceTests(unittest.TestCase):
    def test_endpoint_does_not_duplicate_route(self):
        for url in ('https://example.com/v1', 'https://example.com/v1/images/edits', 'https://example.com/v1/images/generations'):
            self.assertEqual(service.endpoint(url,'/images/edits'),'https://example.com/v1/images/edits')

    def test_proxy_selection_and_local_bypass(self):
        cfg={'base_url':'https://example.com/v1'}
        with patch.object(service,'system_proxies',return_value={'https':'http://127.0.0.1:7890'}):
            self.assertEqual(service.proxy_for(cfg),'http://127.0.0.1:7890')
            self.assertIsNone(service.proxy_for(cfg|{'proxy_mode':'direct'}))
            self.assertEqual(service.proxy_for(cfg|{'proxy_mode':'manual','proxy_url':'http://127.0.0.1:9999'}),'http://127.0.0.1:9999')
            self.assertIsNone(service.proxy_for({'base_url':'http://127.0.0.1:8000/v1'}))

    def test_windows_system_proxy_fallback(self):
        with patch.object(service.sys,'platform','win32'), patch.object(service.urllib.request,'getproxies',return_value={}), patch.object(service.urllib.request,'getproxies_registry',return_value={'https':'http://127.0.0.1:7890'},create=True):
            self.assertEqual(service.system_proxies()['https'],'http://127.0.0.1:7890')

    def test_payload_variants_and_malformed_response(self):
        encoded=base64.b64encode(b'png content').decode()
        self.assertEqual(service.image_payload({'data':[{'b64_json':encoded}]}),b'png content')
        self.assertEqual(service.image_payload({'data':[{'b64_json':'data:image/png;base64,'+encoded}]}),b'png content')
        self.assertEqual(service.image_payload({'data':[{'url':'https://cdn.example/image.png'}]}),'https://cdn.example/image.png')
        for payload in ({},{'data':[]},{'data':[None]},{'data':[{'b64_json':'invalid!!!'}]}):
            with self.assertRaises(ValueError):service.image_payload(payload)

    def test_errors_distinguish_connection_and_redact_credentials(self):
        cfg={'base_url':'https://example.com/v1','proxy_mode':'direct','key':'sensitive-key'}
        self.assertIn('连接图片服务超时',service.connection_error(httpx.ConnectTimeout(''),cfg))
        self.assertIn('避免重复扣费',service.connection_error(httpx.ReadTimeout(''),cfg))
        r=httpx.Response(401,json={'error':{'message':'bad sensitive-key'}})
        with self.assertRaises(ValueError) as caught:service.response_json(r,cfg)
        self.assertNotIn('sensitive-key',str(caught.exception))
        self.assertIn('401',str(caught.exception))
        with self.assertRaisesRegex(ValueError,'没有返回 JSON'):service.response_json(httpx.Response(200,text='<html>Login</html>'),cfg)

    def test_download_does_not_send_api_key(self):
        seen=[]
        def handle(request):
            seen.append(request)
            return httpx.Response(200,content=b'image bytes')
        client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
        async def run():
            with patch.object(service,'image_client',return_value=client):
                self.assertEqual(await service.download_result('https://cdn.example/output.png',{'key':'secret'}),b'image bytes')
        asyncio.run(run())
        self.assertNotIn('authorization',seen[0].headers)


if __name__=='__main__':unittest.main()
