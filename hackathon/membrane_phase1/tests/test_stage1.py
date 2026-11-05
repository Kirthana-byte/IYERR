# Tests Stage 1 HTTP contracts, heading conventions, mock holding, and bad inputs.
# These are mock/API checks, not evidence of a working autonomous physics robot.
from io import BytesIO
import pytest
from PIL import Image
from engine.server import create_app


@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    return app.test_client()


def test_initial_state(client):
    assert client.get('/state').json == dict(state='Idle', x=0, y=0, heading=0, holding=False, retries=0)


def test_clockwise_and_reverse(client):
    assert client.post('/turn', json={'degrees': 90}).json == dict(ok=True, heading=90)
    assert client.post('/move', json={'distance': 2}).json == dict(collided=False, moved=2)
    assert client.get('/state').json['y'] == pytest.approx(-2)
    client.post('/move', json={'distance': -2})
    assert client.get('/state').json['y'] == pytest.approx(0)
    assert client.post('/turn', json={'degrees': -180}).json['heading'] == 270


def test_mock_fetch(client):
    assert client.post('/pickup').json == {'success': False}
    client.post('/move', json={'distance': .6})
    assert client.post('/pickup', json={}).json == {'success': True}
    assert client.get('/state').json['holding'] is True
    assert client.post('/pickup').json == {'success': False}
    client.post('/move', json={'distance': -.6})
    assert client.post('/drop').json == {'in_zone': True}
    assert client.get('/state').json['holding'] is False
    assert client.post('/drop').json == {'in_zone': False}


def test_drop_outside(client):
    client.post('/move', json={'distance': .6})
    client.post('/pickup')
    assert client.post('/drop').json == {'in_zone': False}


@pytest.mark.parametrize('distance,angle,success', [(.6,0,True),(.4,0,False),(.6,40,False)])
def test_mock_reach_and_angle(client, distance, angle, success):
    client.post('/move', json={'distance': distance})
    client.post('/turn', json={'degrees': angle})
    assert client.post('/pickup').json == {'success': success}


def test_sensors(client):
    response = client.get('/look')
    assert response.content_type == 'image/jpeg'
    with Image.open(BytesIO(response.data)) as frame:
        assert frame.format == 'JPEG'
        assert frame.size == (640, 480)
    assert client.get('/depth').json is None


@pytest.mark.parametrize('body', [{}, [], {'distance': True}, {'distance':'1'}, {'distance':None}, {'distance':float('nan')}, {'distance':float('inf')}, {'distance':1,'extra':2}])
def test_reject_bad_move_without_mutation(client, body):
    before = client.get('/state').json
    assert client.post('/move', json=body).status_code == 400
    assert client.get('/state').json == before


def test_invalid_requests(client):
    assert client.post('/move', data='{', content_type='application/json').status_code == 400
    assert client.post('/turn', json={'degrees': False}).status_code == 400
    assert client.post('/pickup', json={'target': 1}).status_code == 400
    assert client.post('/drop', json={'target': 1}).status_code == 400
    assert client.get('/missing').status_code == 404
    assert client.get('/move').status_code == 405
