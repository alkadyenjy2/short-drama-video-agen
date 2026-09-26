import asyncio, hashlib, os, tempfile, unittest
from types import SimpleNamespace
from unittest.mock import patch
import bot

class FakeRepo:
    def __init__(self): self.active=None
    def init_schema(self): pass
    def set_active_video(self,*args): self.active=args; return {}

class FakeFile:
    async def download_to_drive(self,path):
        with open(path,'wb') as f: f.write(b'fake-video-bytes')

class FakeMedia:
    file_unique_id='media-123'
    async def get_file(self): return FakeFile()

class FakeMessage:
    def __init__(self, *, video=None, animation=None, document=None):
        self.video=video; self.animation=animation; self.document=document; self.chat_id=123
        self.replies=[]
    async def reply_text(self,text): self.replies.append(text)

class FakeContext:
    def __init__(self): self.user_data={}

class VideoIngestAudit(unittest.IsolatedAsyncioTestCase):
    async def test_animation_is_ingested_and_verified(self):
        repo=FakeRepo(); msg=FakeMessage(animation=FakeMedia()); update=SimpleNamespace(message=msg,effective_user=SimpleNamespace(id=77)); ctx=FakeContext()
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {'VIDEO_UPLOAD_DIR':td}, clear=False), patch('persistence.repository.get_repository', return_value=repo):
            await bot.handle_video_upload(update,ctx)
            self.assertIn('active_video',ctx.user_data)
            self.assertEqual(ctx.user_data['active_video_bytes'],len(b'fake-video-bytes'))
            self.assertEqual(ctx.user_data['active_video_sha256'],hashlib.sha256(b'fake-video-bytes').hexdigest())
            self.assertEqual(repo.active[0],'77')
            self.assertIn('animation',msg.replies[0])

    async def test_video_document_is_ingested(self):
        repo=FakeRepo(); doc=SimpleNamespace(mime_type='video/mp4',file_unique_id='doc-123',get_file=FakeMedia().get_file); msg=FakeMessage(document=doc); update=SimpleNamespace(message=msg,effective_user=SimpleNamespace(id=88)); ctx=FakeContext()
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {'VIDEO_UPLOAD_DIR':td}, clear=False), patch('persistence.repository.get_repository', return_value=repo):
            await bot.handle_video_upload(update,ctx)
            self.assertEqual(repo.active[0],'88')
            self.assertEqual(ctx.user_data['active_video_id'],'doc-123')
            self.assertIn('document',msg.replies[0])

    def test_handler_registration_covers_video_animation_document(self):
        source=open('bot.py',encoding='utf-8').read()
        self.assertIn('filters.VIDEO | filters.ANIMATION | filters.Document.VIDEO',source)
        self.assertIn('message.animation',source)
        self.assertIn('message.document',source)

if __name__=='__main__': unittest.main()
