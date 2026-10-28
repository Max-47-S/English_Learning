"""Serve the local study package, with byte ranges for accurate MP3 seeking."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import argparse,os,re

class Handler(SimpleHTTPRequestHandler):
    def send_head(self):
        self.remaining=None
        path=self.translate_path(self.path)
        match=re.fullmatch(r'bytes=([0-9]+)-([0-9]*)',self.headers.get('Range',''))
        if not match or not os.path.isfile(path):return super().send_head()
        stream=open(path,'rb');size=os.fstat(stream.fileno()).st_size
        start=int(match[1]);end=min(size-1,int(match[2]) if match[2] else size-1)
        if start>=size or start>end:
            stream.close();self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return None
        self.send_response(206);self.send_header('Content-type',self.guess_type(path))
        self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Range',f'bytes {start}-{end}/{size}');self.end_headers()
        stream.seek(start);self.remaining=end-start+1;return stream
    def copyfile(self,source,outputfile):
        try:
            if self.remaining is None:return super().copyfile(source,outputfile)
            while self.remaining:
                block=source.read(min(1024*1024,self.remaining))
                if not block:break
                outputfile.write(block);self.remaining-=len(block)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8767)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    print(f'Listening on http://{args.host}:{args.port}/ (Ctrl+C to stop)',flush=True)
    ThreadingHTTPServer((args.host,args.port),partial(Handler,directory=str(root))).serve_forever()

if __name__=='__main__':main()
