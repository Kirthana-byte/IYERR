# Checks model-bound text and reports the exact field containing forbidden data.
# Only the typed command and known Claude-authored note fields are exempt.
# Robot pose and the required boolean in_zone result are permitted by the contract.
import copy
import io
import json
import re
from pathlib import Path
from PIL import Image
from .guard import validate_result, validate_frame_name

BANNED = re.compile(
    r'(?i)(?<![a-z])(?:red|blue|green|yellow|orange|purple|pink|white|black|brown|grey|gray|cyan|magenta|'
    r'cube|cuboid|sphere|cylinder|cone|square|circle|triangle|rectangle|ball|box|zone)(?![a-z])'
    r'|target_|cube_|object[_ ]?(?:id|count|position|coordinate|name|colour|color|shape)s?'
    r'|drop[_ ]?zone|segmentation|(?<![a-z])objects(?![a-z])')


def scan(value, path='$'):
    if isinstance(value, dict):
        for key, item in value.items():
            # This mandatory endpoint flag describes delivery, never identity/location.
            if key == 'in_zone' and type(item) is bool:
                continue
            if BANNED.search(str(key)):
                raise ValueError(f'LEAK: {path}.{key} (key)')
            scan(item, f'{path}.{key}')
    elif isinstance(value, list):
        for i, item in enumerate(value): scan(item, f'{path}[{i}]')
    elif isinstance(value, str) and BANNED.search(value):
        raise ValueError(f'LEAK: {path} (text)')


def without_images(value):
    if isinstance(value, dict):
        if value.get('type') == 'image': return {'type':'image','source':'[IMAGE]'}
        return {k:without_images(v) for k,v in value.items()}
    if isinstance(value, list): return [without_images(v) for v in value]
    return value


def scan_request(payload):
    # Work on a copy; the real typed command and notes still reach Claude unchanged.
    value = without_images(copy.deepcopy(payload))
    for i, message in enumerate(value.get('messages', [])):
        for j, block in enumerate(message.get('content', [])):
            if i == 0 and j == 0 and block.get('type') == 'text':
                context = json.loads(block['text'])
                context['command'] = '[USER COMMAND]'
                history = []
                for line in context.get('recent_history', []):
                    event = json.loads(line)
                    if 'visual_memory' in event: event['visual_memory'] = '[MODEL NOTE]'
                    history.append(event)
                context['recent_history'] = history
                block['text'] = context
            elif message.get('role') == 'assistant' and block.get('type') == 'tool_use':
                if 'visual_memory' in block.get('input', {}):
                    block['input']['visual_memory'] = '[MODEL NOTE]'
            elif block.get('type') == 'tool_result':
                for content in block.get('content', []):
                    if content.get('type') == 'text':
                        content['text'] = json.loads(content['text'])
    scan(value)


def scan_endpoint(name, value):
    if name == 'look':
        with Image.open(io.BytesIO(value)) as frame:
            if frame.format != 'JPEG' or frame.size != (640,480):
                raise ValueError('LEAK: endpoint.look (invalid image contract)')
            # Pixel bytes are not text; inspect metadata rather than random byte matches.
            if frame.getexif() or 'comment' in frame.info:
                raise ValueError('LEAK: endpoint.look.metadata')
            scan({k:v for k,v in frame.info.items() if k not in ('jfif','jfif_version','jfif_unit','jfif_density')}, 'endpoint.look.metadata')
        return
    validate_result(name, value)
    scan(value, 'endpoint.'+name)


def scan_log_keys(value, path='$'):
    if isinstance(value, dict):
        for key,item in value.items():
            if key != 'in_zone' and BANNED.search(key):
                raise ValueError(f'LEAK: {path}.{key} (log key)')
            scan_log_keys(item, f'{path}.{key}')
    elif isinstance(value,list):
        for i,item in enumerate(value): scan_log_keys(item, f'{path}[{i}]')


def scan_frame_filename(name):
    scan(name, 'frame.filename')
    if not re.fullmatch(r'(?:step_\d{3,6}|run\d+_step\d{2,6})\.(?:png|jpg)', Path(name).name):
        raise ValueError(f'LEAK: frame.filename (non-neutral name: {name})')
