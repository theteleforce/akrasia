class BasicReactionEvent:
    def __init__(self, message, emoji_names, callback, allowed_users=None, one_time=False, uses=-1):
        if allowed_users is None:
            allowed_users = []

        self.message = message
        self.allowed_users = allowed_users
        if one_time:
            self.uses = 1
        else:
            self.uses = uses

        self.responses = {}
        for emoji_name in emoji_names:
            self.responses[emoji_name] = callback

    @property
    def universal(self):
        return len(self.allowed_users) == 0


class ReactionEvent:
    def __init__(self, *args, allowed_users=None, one_time=False, uses=-1): # *args will either be (message, emoji_name, callback) or (message, response_dict)
        if allowed_users is None:
            allowed_users = []
        if len(args) < 2 or len(args) > 3:
            raise TypeError("ReactionEvent constructors must have either (message, emoji_name, callback) or (message, response_dict) arguments!")

        self.message = args[0]
        if len(args) == 2:
            if args[1] is dict:
                self.responses = args[1]
            else:
                raise TypeError("ReactionEvent constructors must have either (message, emoji_name, callback) or (message, response_dict) arguments!")
        else:
            self.responses = {args[1]: args[2]} # a response dict of {emoji_name: callback}

        self.allowed_users = allowed_users
        if one_time:
            self.uses = 1
        else:
            self.uses = uses

    @property
    def universal(self):
        return len(self.allowed_users) == 0
