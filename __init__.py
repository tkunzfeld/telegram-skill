# Copyright 2018 Lukas Gangel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# TODO: Documentation


import telegram

from alsaaudio import Mixer
from mycroft.skills.core import MycroftSkill
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler
from websocket import create_connection, WebSocket
from mycroft.messagebus.message import Message
from mycroft.api import DeviceApi
from mycroft.audio import wait_while_speaking

loaded = 0

__author__ = "luke5sky"


class TelegramSkill(MycroftSkill):
    def __init__(self):
        super(TelegramSkill, self).__init__(name="TelegramSkill")
        self.is_active = False

    def initialize(self):
        self.telegram_updater = None
        self.mute = str(self.settings.get("MuteIt", ""))
        if (self.mute == "True") or (self.mute == "true"):
            self.mute = True
            try:
                self.mixer = Mixer()
                self.log.info("Telegram Messages will temporarily mute Mycroft.")
            except:
                msg = "There is a problem with alsa audio, mute is not working!"
                self.log.info(msg)
                self.sendMycroftSay(msg)
                self.mute = False
        else:
            self.log.info("Telegram: Muting is off")
            self.mute = False
        self.add_event("telegram-skill:response", self.sendHandler)
        self.add_event("recognizer_loop:wakeword", self.wakewordHandler)
        self.add_event("speak", self.responseHandler)
        user_id1 = self.settings.get("TeleID1", "")
        user_id2 = self.settings.get("TeleID2", "")
        # user_id3 = self.settings.get('TeleID3', '') # makes web-settings too crouded
        # user_id4 = self.settings.get('TeleID4', '') # makes web-settings too crouded
        self.chat_whitelist = [
            user_id1,
            user_id2,
        ]  # ,user_id3,user_id4] # makes web-settings too crouded
        # Get Bot Token from settings.json
        UnitName = DeviceApi().get()["name"]
        MyCroftDevice1 = self.settings.get("MDevice1", "")
        MyCroftDevice2 = self.settings.get("MDevice2", "")
        self.bottoken = ""
        if MyCroftDevice1 == UnitName:
            self.log.debug("Found MyCroft Unit 1: " + UnitName)
            self.bottoken = self.settings.get("TeleToken1", "")
        elif MyCroftDevice2 == UnitName:
            self.log.debug("Found MyCroft Unit 2: " + UnitName)
            self.bottoken = self.settings.get("TeleToken2", "")
        else:
            msg = (
                "No or incorrect Device Name specified! Your DeviceName is: " + UnitName
            )
            self.log.info(msg)
            self.sendMycroftSay(msg)

        # Connection to Telegram API
        try:
            self.telegram_updater = Updater(token=self.bottoken)  # get telegram Updates
            self.telegram_dispatcher = self.telegram_updater.dispatcher
            receive_handler = MessageHandler(
                Filters.text, self.TelegramMessages
            )  # TODO: Make audio Files as Input possible: Filters.text | Filters.audio
            self.telegram_dispatcher.add_handler(receive_handler)
            self.telegram_updater.start_polling(
                clean=True
            )  # start clean and look for messages
            wbot = telegram.Bot(token=self.bottoken)
        except Exception as e:
            self.log.exception("Unable to start telegram bot: {}".format(str(e)))
        if not self.mute:
            self.sendMycroftSay("Telegram Skill is loaded")
        loadedmessage = (
            'Telegram-Skill on Mycroft Unit "'
            + UnitName
            + '" is loaded and ready to use!'
        )  # give User a nice message
        for id in [user_id1, user_id2]:
            self.log.info("Sending welcome message to id {}".format(id))
            try:
                wbot.send_message(
                    chat_id=id, text=loadedmessage
                )  # send welcome message to user 
            except Exception as e:
                self.log.info("Unable to send message to user: {}".format(str(e)))


    def TelegramMessages(self, bot, update):
        msg = update.message.text
        chat_id_test = update.message.chat_id
        self.chat_id = str(update.message.chat_id)
        if self.chat_whitelist.count(chat_id_test) > 0:
            self.is_active = True
            self.log.info("Telegram-Message from User: " + msg)
            msg = (
                msg.replace("\\", " ")
                .replace('"', '\\"')
                .replace("(", " ")
                .replace(")", " ")
                .replace("{", " ")
                .replace("}", " ")
            )
            msg = msg.casefold()  # some skills need lowercase (eg. the cows list)
            # self.add_event('recognizer_loop:audio_output_start', self.muteHandler)
            if self.mute:
                self.mixer.setmute(1)
            self.sendMycroftUtt(msg)

        else:
            self.log.info(
                "Chat ID " + self.chat_id + " is not whitelisted, i don't process it"
            )
            nowhite = "This is your ChatID: " + self.chat_id
            bot.send_message(chat_id=self.chat_id, text=nowhite)

    def sendMycroftUtt(self, msg):
        uri = "ws://localhost:8181/core"
        ws = create_connection(uri)
        utt = (
            '{"context": null, "type": "recognizer_loop:utterance", "data": {"lang": "'
            + self.lang
            + '", "utterances": ["'
            + msg
            + '"]}}'
        )
        ws.send(utt)
        ws.close()

    def sendMycroftSay(self, msg):
        uri = "ws://localhost:8181/core"
        ws = create_connection(uri)
        msg = "say " + msg
        utt = (
            '{"context": null, "type": "recognizer_loop:utterance", "data": {"lang": "'
            + self.lang
            + '", "utterances": ["'
            + msg
            + '"]}}'
        )
        ws.send(utt)
        ws.close()

    def responseHandler(self, message):
        self.log.debug("In response handler")
        if self.is_active == 1:
            response = message.data.get("utterance")
            self.bus.emit(
                Message(
                    "telegram-skill:response",
                    {"intent_name": "telegram-response", "utterance": response},
                )
            )

    def sendHandler(self, message):
        self.log.debug("In send handler")
        sendData = message.data.get("utterance")
        self.log.info("Sending to Telegram-User: " + sendData)
        sendbot = telegram.Bot(token=self.bottoken)
        sendbot.send_message(chat_id=self.chat_id, text=sendData)

    def wakewordHandler(self, message):
        if self.is_active and self.mute:
            self.log.info("Wakeword received, unmuting")
            self.mixer.setmute(0)
        self.is_active = False

    def shutdown(self):  # shutdown routine
        self.log.debug("Shutdown called")
        if self.telegram_updater is not None:
            self.telegram_updater.stop()  # will stop update and dispatcher
            self.telegram_updater.is_idle = False
        super(TelegramSkill, self).shutdown()

    def stop(self):
        self.log.debug("Stop called")
        self.is_active = False
        if self.mute:
            self.mixer.setmute(0)


def create_skill():
    return TelegramSkill()
