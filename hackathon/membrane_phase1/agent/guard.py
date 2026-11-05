# Enforces the narrow observation contract before any engine data reaches Claude.
# This is schema validation, not an unreliable blacklist of English colour words.
import math
import re

STATES={'Idle','Locate','Go to object','Pick up','Carry','Drop','Done','Blocked'}
SCHEMAS={
    'state':{'state':str,'x':float,'y':float,'heading':float,'holding':bool,'retries':int},
    'move':{'collided':bool,'moved':float},
    'turn':{'ok':bool,'heading':float},
    'pickup':{'success':bool},
    'drop':{'in_zone':bool},
}


def numeric(value):
    return type(value) in (int,float) and math.isfinite(value)


def validate_result(name, value):
    if name=='depth':
        if value is not None and (not numeric(value) or not 0<=value<=10):
            raise ValueError('Invalid range sensor response')
        return value
    schema=SCHEMAS[name]
    if not isinstance(value,dict) or set(value)!=set(schema):
        raise ValueError('Unexpected engine response fields')
    for key,expected in schema.items():
        item=value[key]
        valid=numeric(item) if expected is float else type(item) is expected
        if not valid:
            raise ValueError('Unexpected engine response type')
    if name=='state':
        if value['state'] not in STATES or not 0<=value['retries']<=3:
            raise ValueError('Invalid robot state')
    return value


def validate_frame_name(name):
    if not re.fullmatch(r'step_\d{3}\.png',name):
        raise ValueError('Non-neutral frame name')
