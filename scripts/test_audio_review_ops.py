"""Isolated technical audio-review regression tests; no semantic hearing claims."""
import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from common import run_ffmpeg,save_json,load_json,sha256
from audio_review_ops import prepare

class AudioReviewTest(unittest.TestCase):
 def test_review_extract_preserve_and_reject_unknown(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);media=root/'synthetic.mp4'
   run_ffmpeg(['-y','-f','lavfi','-i','color=c=red:size=160x90:rate=30:duration=1','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=1','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',media])
   digest=sha256(media)
   save_json(root/'.remix/rendered.json',{'videos':[{'video_id':'01','path':media.name,'sha256':digest,'passed':True}]})
   save_json(root/'.remix/usage.json',{'segment_uses':{'test':1}})
   quota=(root/'.remix/usage.json').read_bytes()
   args=SimpleNamespace(project=str(root),only=None,extract=True);prepare(args)
   path=root/'.remix/audio-review.json';data=load_json(path);row=data['videos'][0]
   self.assertEqual(len(data['options']),3)
   self.assertTrue((root/row['listening_audio']).is_file())
   self.assertTrue((root/row['technical_timeline']).is_file())
   self.assertEqual(set(row['composition'].values()),{'not_semantically_reviewed'})
   row['status']='user_chose_keep_original';save_json(path,data);args.extract=False;prepare(args)
   self.assertEqual(load_json(path)['videos'][0]['status'],'user_chose_keep_original')
   before=path.read_bytes();args.only='unknown'
   with self.assertRaisesRegex(ValueError,'Unknown final video ID'):prepare(args)
   self.assertEqual(path.read_bytes(),before)
   args.only=None;media.write_bytes(media.read_bytes()+b'changed')
   with self.assertRaisesRegex(ValueError,'unchanged verified final'):prepare(args)
   self.assertEqual(path.read_bytes(),before)
   self.assertEqual((root/'.remix/usage.json').read_bytes(),quota)

if __name__=='__main__':unittest.main()
