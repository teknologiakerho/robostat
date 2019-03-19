from robostat.ruleset import Ruleset

class HaastatteluRuleset:

    def create_score(self):
        return False

    def decode(self, data):
        return bool(data[0])

    def encode(self, score):
        return bytes([int(score)])
