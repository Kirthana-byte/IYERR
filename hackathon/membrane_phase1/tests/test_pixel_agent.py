# Tests pixel-only perception with rendered synthetic images, not scene metadata.
import ast
import io
from pathlib import Path
import pytest
from PIL import Image,ImageDraw
cv2=pytest.importorskip('cv2',reason='Optional pixel dependency not installed')
from agent.pixel_agent import parse,detect,decide


def test_supported_commands_and_rejection():
    assert parse('Bring the red cube to the green square')==('red','cube','green')
    assert parse('Bring the round red thing to the green square')==('red','sphere','green')
    with pytest.raises(ValueError,match='supported'):parse('Bring the tallest object')


def test_masks_disambiguate_same_colour_shapes():
    image=Image.new('RGB',(640,480),(130,130,130));draw=ImageDraw.Draw(image)
    draw.rectangle((70,180,150,260),fill=(220,0,0))
    draw.ellipse((390,180,470,260),fill=(220,0,0))
    data=io.BytesIO();image.save(data,'JPEG')
    cube=detect(data.getvalue(),'red','cube');sphere=detect(data.getvalue(),'red','sphere')
    assert cube['cx']<320 and sphere['cx']>320
    name,args,_,_=decide(data.getvalue(),False,'red','cube','green',None,0)
    assert name=='turn' and args['degrees']<0


def test_pixel_module_cannot_import_scene():
    source=Path('agent/pixel_agent.py').read_text()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node,ast.Import):names=[n.name for n in node.names]
        elif isinstance(node,ast.ImportFrom):names=[node.module or '']
        else:continue
        assert not any(n.split('.')[0] in ('engine','pybullet','scene') for n in names)


def test_hygiene_scanner_reports_location_without_secret(tmp_path):
    from check_hygiene import scan
    key='sk-'+'ant-'+'a'*30
    (tmp_path/'bad.py').write_text('key='+repr(key))
    _,failures=scan(tmp_path)
    assert failures and 'bad.py:1' in failures[0]
    assert key not in failures[0]
