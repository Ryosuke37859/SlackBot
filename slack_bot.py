#! /usr/bin/env Python3

import os
import time
import re
from slackclient import SlackClient


class SlackHandler():
    def __init__(self, token, commands, exact=True):
        # instantiate Slack client
        self._client = SlackClient(token)
        self._mention_regex = "^<@(|[WU].+?)>(.*)"
        # bot's user ID in Slack: value is assigned after the bot starts up
        self._id = None
        # Command list takes following format: [{"command":"do", "description": "do something"}, ...]
        self.commands = commands
        self.read_delay = 1
        self.default_response = "Not sure what you mean. Try *{}*.".format("help")
        self.command_out = []
        self.command_in = []
        self.exact_match = exact
    
    
    def start(self):
        self._client.rtm_connect(with_team_state=False)
        self._id = self._client.api_call("auth.test")["user_id"]


    def parse_direct_mention(self, message_text):
        """
            Finds a direct mention (a mention that is at the beginning) in message text
            and returns the user ID which was mentioned. If there is no direct mention, returns None
        """
        matches = re.search(self._mention_regex, message_text)
        # the first group contains the username, the second group contains the remaining message
        return (matches.group(1), matches.group(2).strip()) if matches else (None, None)
    
    
    def parse_whisper(self, message_text):
        """
            Determines whether or not the Requesting user wants the reply to be ephemeral.
        """
        if "whisper" in message_text:
            return True, message_text.replace("whisper","").strip()
        else:
            return False, message_text
                                    
    
    def send_message(self, channel, message):
        """
            Sends a message to a Slack Channel
        """
        self._client.api_call(
            "chat.postMessage",
            channel=channel,
            text=message)
        return True
    
    
    def send_ephemeral_message(self, channel, user, message):
        """
            Sends Ephemeral Message to user
        """
        self._client.api_call(
            "chat.postEphemeral",
            channel=channel,
            text=message,
            user=user)
        return True
        
        
    def reply(self, channel, thread_ts, message):
        """
            Sends Reply to thread
        """
        if self._client.api_call(
            "chat.postMessage",
            channel=channel,
            text=message,
            thread_ts=thread_ts):
            return True
        else:
            return False
    
    
    def match_command(self, user_command):
        """ Matches command and creates a response"""
        response = None
        
        if user_command == "help":
            response = ""
            for command, description in [x.values() for x in self.commands]:
                response += "\n*%s*:" % command
                response += "\n%s\n" % description
        else:
            # Exact Match, default
            if self.exact_match:
                for command, description in [x.values() for x in self.commands]:
                    if user_command == command.lower():
                        response = "Running command..."
                        break
            # Longest Match first, pay extra attention to command order and validation if using this
            # This allows for passing arguments after the command string
            else: 
                for command, description in [x.values() for x in self.commands]:
                    if command.lower() in user_command:
                        response = "Running command..."
                        break
        
        return response
    
    
    def handle_command(self, message):
        """
            Returns bot command if the command is known
        """
        user_command = message["command"].lower().strip()
        # Default response is help text for the user
        
        message["whisper"], message["command"] = self.parse_whisper(user_command)

        # Finds and executes the given command, filling in response
        response = self.match_command(message["command"])
                
        if not response:
            response = self.default_response
        
        # Sends the response back to the channel
        if message["whisper"]:
            self.send_ephemeral_message(
                channel=message["channel"],
                message=response,
                user=message["user"]
            )
        else:
            self.reply(
                channel=message["channel"],
                message=response,
                thread_ts=message["ts"]
            )
        
        if message["command"] != "help" and response != self.default_response:
            self.command_out.append(message)
                
        return True
        
        
    def parse_bot_commands(self):
        """
            Parses a list of events coming from the Slack RTM API to find bot commands.
            If a bot command is found, this function returns a tuple of command and channel.
            If its not found, then this function returns None, None.
        """
        slack_events = self._client.rtm_read()
        for event in slack_events:
            if event["type"] == "message" and not "subtype" in event:
                dest_user_id, message = self.parse_direct_mention(event["text"])
                if dest_user_id == self._id:
                    self.command_in.append(
                    {"channel": event["channel"],
                    "ts": event["ts"],
                    "user": event["user"],
                    "command": message.lower()})
        
        return True
    
    
    def process_command_in(self):
        """Processes commands that has been placed in the self.command_in queue"""
        for command in self.command_in:
            self.handle_command(command)
            self.command_in.remove(command)
        
        return True
        
    
    def heartbeat(self):
        """
            Checks to see if api connection is working
        """
        if self._client.api_call("api.test")["ok"] == True:
            return True
        else:
            return False


if __name__ == "__main__":
    token = os.environ.get('SLACK_BOT_TOKEN')
    commands = [{"command":"do", "description": "do something"}]
    # Example Execution loop
    client = SlackHandler(token=token, commands=commands)
    client.start()
    print("Starter Bot connected and running!")
    while True:
        client.parse_bot_commands()
        client.process_command_in()
        while client.command_out:
            print("command: %s" % client.command_out.pop(0))
        time.sleep(1)

