#!/usr/bin/env python3

import io
import logging
import netifaces
import os
from enum import Enum

import emoji
import telegram
import zmq

import settings
from message_handler import MessageHandler


class Commands(Enum):
    START = 1
    VIDEO_STREAM = 2
    SNAPSHOT = 3
    STATS = 4
    REBOOT = 5
    SHUTDOWN = 6

    def __str__(self):
        if self.value == 1:
            return '/start'
        elif self.value == 2:
            return 'video stream'
        elif self.value == 3:
            return 'snapshot'
        elif self.value == 4:
            return 'statistics'
        elif self.value == 5:
            return 'reboot'
        elif self.value == 6:
            return 'shutdown'


def emojize(idx):
    return emoji.emojize(':{}:'.format(idx.strip(':')), use_aliases=True)


mh = MessageHandler(token=settings.TELEGRAM_TOKEN,
                    chat_id=settings.CHAT_ID,
                    commands=[str(c) for c in Commands],
                    queries=['confirm_shutdown',
                             'abort_shutdown',
                             'confirm_reboot',
                             'abort_reboot'])


@mh.register_callback(str(Commands.START))
def handle_cmd_start(bot, update):
    emoji = emojize('wave')
    bot.send_message(chat_id=update.message.chat_id,
                     text='Hey There{} '
                          'You just have successfully started your personal Babyphone Knecht.'.format(emoji))

    keyboard = [
        ['Video Stream', 'Snapshot'],
        ['Statistics', ],
        ['Reboot', 'Shutdown', ],
    ]
    bot.send_message(chat_id=update.message.chat_id,
                     text='Use the dedicated keyboard to enter your commands.',
                     reply_markup=telegram.ReplyKeyboardMarkup(keyboard))


@mh.register_callback(str(Commands.VIDEO_STREAM))
def handle_cmd_video_stream(bot, update):
    interface = settings.NET_INTERFACE
    ip = netifaces.ifaddresses(interface)[netifaces.AF_INET][0]['addr']
    port = '8080'
    url = '{}:{}/'.format(ip, port)
    emoji = emojize('computer')
    bot.send_message(chat_id=update.message.chat_id,
                     text='The Video live stream is available at [{}]({}) {}'.format(url, url, emoji),
                     parse_mode=telegram.ParseMode.MARKDOWN)


@mh.register_callback(str(Commands.SNAPSHOT))
def handle_cmd_snapshot_stream(bot, update):
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    try:
        socket.connect(settings.CAMERA_SOCKET)
        socket.send_string('')
        binary_img = socket.recv()
        bot.send_photo(chat_id=update.message.chat_id, photo=io.BytesIO(binary_img))
    except Exception as e:
        logging.error('Could not get and send snapshot. Error message was: \'{}\''.format(str(e)))


@mh.register_callback(str(Commands.STATS))
def handle_cmd_stats(bot, update):
    uptime = os.popen('/usr/bin/uptime -p').read().lstrip('up').strip()
    emoji = emojize('alarm_clock')
    bot.send_message(chat_id=update.message.chat_id,
                     text='{} Uptime: {}'.format(emoji, uptime),
                     parse_mode=telegram.ParseMode.MARKDOWN)


def make_inline_keyboard(labels, callback_data):
    return telegram.InlineKeyboardMarkup(
        [[telegram.InlineKeyboardButton(label, callback_data=data) for (label, data) in zip(labels, callback_data)], ])


@mh.register_callback(str(Commands.SHUTDOWN))
def handle_cmd_shutdown(bot, update):
    logging.info('User %d requested shutdown.', update.effective_user.id)
    buttons = make_inline_keyboard(['Confirm', 'Abort'], ['confirm_shutdown', 'abort_shutdown'])
    emoji = emojize('point_up')
    bot.send_message(chat_id=update.message.chat_id,
                     text='Please confirm shutdown {}'.format(emoji),
                     reply_markup=buttons)


@mh.register_callback(str(Commands.REBOOT))
def handle_cmd_reboot(bot, update):
    logging.info('User %d requested reboot.', update.effective_user.id)
    buttons = make_inline_keyboard(['Confirm', 'Abort'], ['confirm_reboot', 'abort_reboot'])
    emoji = emojize('point_up')
    bot.send_message(chat_id=update.message.chat_id,
                     text='Please confirm reboot {}'.format(emoji),
                     reply_markup=buttons)


@mh.register_query_callback('confirm_shutdown')
def handle_query_confirm_shutdown(bot, update):
    logging.info('User %d confirmed shutdown.', update.effective_user.id)
    os.system('/usr/bin/sudo shutdown -h now')


@mh.register_query_callback('abort_shutdown')
def handle_query_abort_shutdown(bot, update):
    logging.info('User %d aborted shutdown.', update.effective_user.id)


@mh.register_query_callback('confirm_reboot')
def handle_query_confirm_reboot(bot, update):
    logging.info('User %d confirmed reboot.', update.effective_user.id)
    os.system('/usr/bin/sudo reboot')


@mh.register_query_callback('abort_reboot')
def handle_query_abort_reboot(bot, update):
    logging.info('User %d aborted reboot.', update.effective_user.id)


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=settings.LOG_LEVEL)

    mh.run()
