from email.message import Message
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from time import monotonic
from unittest import TestCase
from unittest.mock import patch

from autonomous_company import CompanyError
from official_media import _global_addresses, download_mp4, official_url


class Response(BytesIO):
    def __init__(self, code, content_type, body):
        super().__init__(body)
        self.status=code
        self.headers=Message()
        self.headers['Content-Type']=content_type
        self.headers['Content-Length']=str(len(body))
        self.headers['Location']='https://other.example/replacement.mp4'

    def getheader(self,name,default=None):
        return self.headers.get(name,default)


class OfficialMediaTests(TestCase):
    def test_rejects_unsafe_urls_and_private_or_mixed_dns(self):
        for url in ('http://publisher.example/asset.mp4','https://publisher.example:444/asset.mp4',
                    'https://user@publisher.example/asset.mp4','https://publisher.example/a/../asset.mp4',
                    'https://publisher.example/%2e%2e/asset.mp4','https://publisher.example/asset.mp4?token=x',
                    'https://127.0.0.1/asset.mp4','https://youtube.com/asset.mp4'):
            with self.assertRaisesRegex(CompanyError,'official_url_blocked'):
                official_url(url,media=True)
        public=(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',443))
        for blocked in ('127.0.0.1','10.1.2.3','169.254.169.254','224.0.0.1'):
            with patch('official_media.socket.getaddrinfo',return_value=[public,(*public[:4],(blocked,443))]):
                with self.assertRaisesRegex(CompanyError,'official_destination_blocked'):
                    _global_addresses('publisher.example',monotonic()+2)
        with patch('official_media.socket.getaddrinfo',return_value=[public]):
            self.assertEqual(_global_addresses('publisher.example',monotonic()+2), (socket.AF_INET,public[-1]))

    def test_one_get_rejects_redirects_wrong_type_size_and_hash(self):
        payload=b'fixture MP4 content'
        asset=dict(url='https://publisher.example/asset.mp4',sha256=sha256(payload).hexdigest())
        for code,kind,body,reason in ((302,'video/mp4',payload,'official_media_response_invalid'),
                                      (200,'text/html',payload,'official_media_response_invalid'),
                                      (200,'video/mp4',b'different','production_source_asset_changed'),
                                      (200,'video/mp4',b'','official_media_size_invalid'),
                                      (200,'video/mp4',payload,None)):
            with TemporaryDirectory() as folder, patch('official_media._global_addresses',
                    return_value=(socket.AF_INET,('8.8.8.8',443))), patch('official_media._PinnedHTTPS') as connection:
                receiver=connection.return_value
                receiver.getresponse.return_value=Response(code,kind,body)
                target=Path(folder)/'asset.mp4'
                if reason:
                    with self.assertRaisesRegex(CompanyError,reason):
                        download_mp4(asset,target)
                else:
                    self.assertEqual(download_mp4(asset,target)['sha256'],asset['sha256'])
                    self.assertEqual(target.read_bytes(),payload)
                receiver.request.assert_called_once_with('GET','/asset.mp4',headers={
                    'Accept':'video/mp4','Accept-Encoding':'identity'})

    def test_editor_rejects_repeated_assets_out_of_range_cut_and_unknown_asset(self):
        from asset_editing import AssetEditor

        catalog={'official:hook':{'frames':144},'local:body':{'frames':None}}
        rows=[dict(scene_id='scene-1',frames=100),dict(scene_id='scene-2',frames=200)]
        with TemporaryDirectory() as folder:
            editor=AssetEditor(Path(folder),dict(input=dict(scenes=rows,candidates=catalog)))
            first=dict(scene_id='scene-1',asset_id='official:hook',in_frame=12,framing='letterbox_top',
                       transition='cut',caption_position='safe_upper',suitability='상단 프레이밍과 도입부 확인')
            second={**first,'scene_id':'scene-2','asset_id':'local:body','in_frame':0}
            result=dict(action='edit',review_criteria='시청과 자막 검토',scenes=[first,second])
            editor.validate_plan(result)
            for start,selected in ((45,'local:body'),(12,'official:hook'),(12,'official:unlisted')):
                with self.assertRaisesRegex(CompanyError,'invalid_source_edit'):
                    editor.validate_plan({**result,'scenes':[{**first,'in_frame':start},{**second,'asset_id':selected}]})
