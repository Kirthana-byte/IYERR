# Tracks the fetch lifecycle using simulation time only.
# Blocked is reserved for motion collisions and two seconds of simulated stall.
# Pickup attempts are counted separately and never consume motion recovery retries.
class StateMachine:
    def __init__(self, on_transition=None):
        self.on_transition=on_transition
        self.name = 'Idle'
        self.retries = 0
        self.pickup_attempts = 0
        self.outcome = None
        self.failure_outcome = 'fail_collision'
        self.stalled_seconds = 0.0
        self.transitions = ['Idle']

    def enter(self, name):
        if self.name != name:
            before=self.name
            self.name = name
            self.transitions.append(name)
            if self.on_transition:
                self.on_transition(before,name,self.retries)

    def begin(self):
        self.enter('Locate')

    def block(self, outcome='fail_collision'):
        self.failure_outcome = outcome
        self.enter('Blocked')
        if self.retries >= 3:
            self.finish(self.failure_outcome)

    def recovery(self):
        if self.name != 'Blocked':
            return None
        if self.retries >= 3:
            self.finish(self.failure_outcome)
            return None
        angle = (45.0, -90.0, 135.0)[self.retries]
        self.retries += 1
        return angle

    def progress(self, moved, seconds):
        self.stalled_seconds = 0.0 if moved > 1e-8 else self.stalled_seconds + seconds
        if self.stalled_seconds >= 2.0:
            self.block()

    def finish(self, outcome):
        if self.name != 'Done':
            self.outcome = outcome
            self.enter('Done')
