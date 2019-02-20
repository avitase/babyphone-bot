#!/usr/bin/env python3

import logging
import netifaces
import os
from enum import Enum
from functools import partial

import telegram
from telegram.ext import Updater, BaseFilter, MessageHandler, Filters, CallbackQueryHandler

import settings


def make_inline_keyboard(labels, callback_data):
    return telegram.InlineKeyboardMarkup(
        [[telegram.InlineKeyboardButton(label, callback_data=data) for (label, data) in zip(labels, callback_data)], ])


class Commands(Enum):
    START = 1
    VIDEO_STREAM = 2
    STATS = 3
    REBOOT = 4
    SHUTDOWN = 5

    def __str__(self):
        if self.value == 1:
            return '/start'
        elif self.value == 2:
            return 'video stream'
        elif self.value == 3:
            return 'statistics'
        elif self.value == 4:
            return 'reboot'
        elif self.value == 5:
            return 'shutdown'
        return 'unknown'


class KnownCommandFilter(BaseFilter):
    def filter(self, message):
        cmd = message.text.lower().strip()
        for c in Commands:
            if str(c) == cmd: return True
        return False


def print_authentication_error(bot, message, user_id=None):
    if user_id:
        logging.warning('Unauthorized access denied for user %d.', user_id)
    bot.send_message(chat_id=message.chat_id,
                     text='Sorry, your chat id {} is invalid! '
                          'This chat is not authorized to use the Babyphone Knecht.'.format(message.chat_id))


def default_callback(bot, update, chat_id):
    msg = update.message

    if msg.chat_id != chat_id:
        print_authentication_error(bot, msg, update.effective_user.id)
    else:
        cmd = None
        for c in Commands:
            if str(c) == msg.text.lower().strip():
                cmd = c
                break

        assert cmd is not None

        handler = None
        if cmd == Commands.START:
            handler = handle_cmd_start
        elif cmd == Commands.VIDEO_STREAM:
            handler = handle_cmd_video_stream
        elif cmd == Commands.STATS:
            handler = handle_cmd_stats
        elif cmd == Commands.SHUTDOWN:
            handler == handle_cmd_shutdown
        elif cmd == Commands.REBOOT:
            handler = handle_cmd_reboot

        handler(bot, update)


def handle_cmd_start(bot, update):
    bot.send_message(chat_id=update.message.chat_id,
                     text='Hey There! You just have successfully started your personal Babyphone Knecht.')

    keyboard = [
        ['Video Stream', ],
        ['Statistics', ],
        ['Reboot', 'Shutdown', ],
    ]
    bot.send_message(chat_id=update.message.chat_id,
                     text='Use the keyboard to enter your commands.',
                     reply_markup=telegram.ReplyKeyboardMarkup(keyboard))


def handle_cmd_video_stream(bot, update):
    interface = settings.NET_INTERFACE
    ip = netifaces.ifaddresses(interface)[netifaces.AF_INET][0]['addr']
    port = '8080'
    url = '{}:{}/'.format(ip, port)
    bot.send_message(chat_id=update.message.chat_id,
                     text='The Video live stream is available at [{}]({})'.format(url, url),
                     parse_mode=telegram.ParseMode.MARKDOWN)


def handle_cmd_stats(bot, update):
    uptime = os.popen('/usr/bin/uptime -p').read().lstrip('up').strip()
    bot.send_message(chat_id=update.message.chat_id,
                     text='Uptime: {}'.format(uptime),
                     parse_mode=telegram.ParseMode.MARKDOWN)


def handle_cmd_shutdown(bot, update):
    logging.info('User %d requested shutdown.', update.effective_user.id)
    buttons = make_inline_keyboard(['Confirm', 'Abort'], ['confirm_shutdown', 'abort_shutdown'])
    bot.send_message(chat_id=update.message.chat_id,
                     text='Please confirm shutdown',
                     reply_markup=buttons)


def handle_cmd_reboot(bot, update):
    logging.info('User %d requested reboot.', update.effective_user.id)
    buttons = make_inline_keyboard(['Confirm', 'Abort'], ['confirm_reboot', 'abort_reboot'])
    bot.send_message(chat_id=update.message.chat_id,
                     text='Please confirm reboot',
                     reply_markup=buttons)


def button(bot, update, chat_id):
    if update.callback_query.message.chat_id != chat_id:
        print_authentication_error(bot, update.callback_query.message)
    else:
        callback_data = update.callback_query.data

        bot.delete_message(chat_id=update.callback_query.message.chat_id,
                           message_id=update.callback_query.message.message_id)

        user_id = update.effective_user.id
        if callback_data == 'confirm_shutdown':
            logging.info('User %d confirmed shutdown.', user_id)
            os.system('/usr/bin/sudo shutdown -h now')
        elif callback_data == 'abort_shutdown':
            logging.info('User %d aborted shutdown.', user_id)
        elif callback_data == 'confirm_reboot':
            os.system('/usr/bin/sudo reboot')
            logging.info('User %d confirmed reboot.', user_id)
        elif callback_data == 'abort_reboot':
            logging.info('User %d aborted reboot.', user_id)


def unknown(bot, update):
    bot.send_message(chat_id=update.message.chat_id,
                     text="Sorry, I didn't understand that command.")


if __name__ == '__main__':
    token = settings.TELEGRAM_TOKEN
    assert token

    chat_id = settings.CHAT_ID
    assert chat_id

    log_level = settings.LOG_LEVEL
    assert log_level
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=log_level)

    updater = Updater(token=token)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(MessageHandler(KnownCommandFilter(), partial(default_callback, chat_id=chat_id)))
    dispatcher.add_handler(MessageHandler(Filters.command, unknown))

    dispatcher.add_handler(CallbackQueryHandler(partial(button, chat_id=chat_id)))

    updater.start_polling()
