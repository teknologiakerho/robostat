class ValidationError(Exception):
    pass

class Ruleset:

    num_teams = 1

    def create_score(self):
        raise NotImplementedError

    def decode(self, data):
        raise NotImplementedError

    def encode(self, score):
        raise NotImplementedError

    def validate(self, *scores):
        pass
