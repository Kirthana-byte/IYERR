# Exposes the seven robot endpoints on the loopback interface at port 8080.
# Validates inputs before changing state and serializes robot access with a lock.
# CLI selects MockRobot or the full PyBullet backend; API keys are never used here.
import math
from threading import Lock
from flask import Flask, Response, jsonify, request
from werkzeug.exceptions import HTTPException
from .mock_robot import MockRobot
from .robot import Robot


def create_app(robot: Robot | None = None):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 4096
    robot = robot if robot is not None else MockRobot()
    lock = Lock()

    def number_body(key):
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) != {key}:
            raise ValueError('Expected one numeric field: ' + key)
        value = data[key]
        if type(value) not in (int, float):
            raise ValueError('Expected a finite number')
        try:
            value = float(value)
        except OverflowError:
            raise ValueError('Expected a finite number') from None
        if not math.isfinite(value):
            raise ValueError('Expected a finite number')
        if abs(value) > (10 if key == 'distance' else 360):
            raise ValueError('Action exceeds per-call limit')
        return value

    def empty_body():
        if request.get_data() and request.get_json(silent=True) != {}:
            raise ValueError('Expected an empty body or an empty JSON object')

    @app.errorhandler(ValueError)
    def invalid_input(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.name), error.code

    @app.get('/state')
    def state():
        with lock:
            return jsonify(robot.state())

    @app.get('/look')
    def look():
        with lock:
            return Response(robot.look(), mimetype='image/jpeg', headers={'Cache-Control': 'no-store'})

    @app.get('/depth')
    def depth():
        with lock:
            return jsonify(robot.depth())

    @app.post('/move')
    def move():
        distance = number_body('distance')
        with lock:
            return jsonify(robot.move(distance))

    @app.post('/turn')
    def turn():
        degrees = number_body('degrees')
        with lock:
            return jsonify(robot.turn(degrees))

    @app.post('/pickup')
    def pickup():
        empty_body()
        with lock:
            return jsonify(robot.pickup())

    @app.post('/drop')
    def drop():
        empty_body()
        with lock:
            return jsonify(robot.drop())

    return app


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    from werkzeug.serving import make_server
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=['mock','pybullet'], default='pybullet')
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--fast', action='store_true', help='Unpaced physics for automated tests')
    parser.add_argument('--command', default='')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--report')
    parser.add_argument('--record-pov',action='store_true')
    parser.add_argument('--stop-file')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    if args.backend == 'mock':
        robot = MockRobot()
    else:
        from .pybullet_robot import PyBulletRobot
        robot = PyBulletRobot(gui=args.gui, command=args.command, seed=args.seed,
                             realtime=not args.fast, report=args.report, record_pov=args.record_pov)
    # Single owner thread keeps all Bullet calls, GUI and HTTP mutations serialized.
    server = make_server('127.0.0.1', args.port, create_app(robot))
    server.timeout = .02
    print(f'Backend: {args.backend}. Listening on http://127.0.0.1:{args.port}', flush=True)
    try:
        while True:
            if args.stop_file and Path(args.stop_file).exists():
                if hasattr(robot, 'finish'):
                    robot.finish()
                break
            server.handle_request()
    except KeyboardInterrupt:
        if hasattr(robot, 'finish'):
            robot.finish()
    finally:
        server.server_close()
        if hasattr(robot, 'close'):
            robot.close()
