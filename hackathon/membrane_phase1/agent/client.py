# Talks to the engine only through HTTP. No scene modules or private reports enter here.
# Responses are validated and errors are generic so engine exception text cannot leak.
import io
import json
from datetime import datetime,timezone
import requests
from PIL import Image
from .guard import validate_result


class RobotClient:
    def __init__(self, base='http://127.0.0.1:8080'):
        self.base=base
        self.session=requests.Session()
        self.session.trust_env=False
        self.log_path=None
        self.sequence=0

    def call(self,name,args=None):
        try:
            if args is None:
                response=self.session.get(self.base+'/'+name,timeout=120)
            else:
                response=self.session.post(self.base+'/'+name,json=args,timeout=120)
            response.raise_for_status()
        except requests.RequestException:
            raise RuntimeError('Robot HTTP request failed') from None
        if name=='look':
            if response.headers.get('Content-Type','').split(';')[0]!='image/jpeg':
                raise ValueError('Expected JPEG')
            with Image.open(io.BytesIO(response.content)) as image:
                if image.format!='JPEG' or image.size!=(640,480):
                    raise ValueError('Unexpected image format')
                # Re-encode to strip JPEG comments/EXIF and any accidental metadata.
                output=io.BytesIO()
                image.convert('RGB').save(output,'JPEG',quality=90)
                result=output.getvalue()
                self._record(name, {'format':'JPEG','width':640,'height':480})
                return result
        try:
            result=validate_result(name,response.json())
            self._record(name,result)
            return result
        except (ValueError,KeyError):
            raise ValueError('Engine response violated observation contract') from None

    def _record(self,name,result):
        # Local evidence only; this file is never read into the model context.
        if self.log_path is None: return
        self.sequence+=1
        with self.log_path.open('a',encoding='utf-8') as out:
            out.write(json.dumps({'sequence':self.sequence,
                'timestamp':datetime.now(timezone.utc).isoformat(),
                'endpoint':name,'result':result})+'\n')
