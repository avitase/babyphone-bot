#!/usr/bin/env python3

import argparse
import logging
import netifaces
import os
from functools import wraps

import telegram
from telegram.ext import Updater, BaseFilter, Filters, CommandHandler, MessageHandler, CallbackQueryHandler

chat_id = None

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)


def read_telegram_token(token_file_name='telegram-token.txt'):
    with open(token_file_name, 'r') as f:
        return f.readline().strip()


def get_ip(interface):
    return netifaces.ifaddresses(interface)[netifaces.AF_INET][0]['addr']


class KnownCommand(BaseFilter):
    commands = {
        '/help': 'help',
        '/stream_url': 'URL of Live-Stream',
        '/reboot': 'Reboot',
        '/shutdown': 'Shutdown',
    }

    def filter(self, message):
        if message.text in self.commands: return True
        return message.text in [self.commands[key] for key in self.commands]


known_cmd_filter = KnownCommand()


def start(bot, update, args, pin):
    global chat_id
    if chat_id is None \
            and len(args) == 1 \
            and args[0].isdigit() \
            and int(args[0]) == pin:

        chat_id = update.message.chat_id
        bot.send_message(chat_id=update.message.chat_id,
                         text='Hey There! You just have successfully started your personal Babyphone Knecht.')

        cmds = known_cmd_filter.commands
        keyboard = [
            [cmds['/stream_url'], ],
            [cmds['/reboot'], cmds['/shutdown'], ],
        ]
        bot.send_message(chat_id=update.message.chat_id,
                         text='Use the keyboard to enter your commands.',
                         reply_markup=telegram.ReplyKeyboardMarkup(keyboard))
    else:
        bot.send_message(chat_id=update.message.chat_id,
                         text='Sorry, I could not authenticate you via PIN! '
                              'Please restart me and pass a valid PIN.')


def check_authentication(f):
    @wraps(f)
    def wrapper(bot, update, *args, **kwargs):
        if update.message.chat_id == chat_id:
            f(bot, update, *args, **kwargs)
        else:
            logging.warning('Unauthorized access denied for %d.', update.effective_user.id)
            bot.send_message(chat_id=update.message.chat_id,
                             text='Sorry, I could not authenticate you via PIN! '
                                  'Please restart me and pass a valid PIN.')

    return wrapper


@check_authentication
def usage(bot, update):
    bot.send_message(chat_id=update.message.chat_id,
                     text='Hello, I am your friendly Babyphone Knecht. '
                          'Use the keyboard to enter your commands.')


@check_authentication
def default_callback(bot, update):
    message = update.message.text
    cmds = known_cmd_filter.commands
    if message in ['/stream_url', cmds['/stream_url']]:
        ip = get_ip('wlan0')
        port = '8080'
        url = '{}:{}/'.format(ip, port)
        bot.send_message(chat_id=update.message.chat_id,
                         text='[{}]({})'.format(url, url),
                         parse_mode=telegram.ParseMode.MARKDOWN)

    elif message in ['/shutdown', cmds['/shutdown']]:
        logging.info('User %d requested shutdown.', update.effective_user.id)
        yes_no_buttons = [
            [telegram.InlineKeyboardButton('Confirm', callback_data='confirm_shutdown'),
             telegram.InlineKeyboardButton('Abort', callback_data='abort_shutdown'), ],
        ]
        bot.send_message(chat_id=update.message.chat_id,
                         text='Please confirm shutdown',
                         reply_markup=telegram.InlineKeyboardMarkup(yes_no_buttons))

    elif message in ['/reboot', cmds['/reboot']]:
        logging.info('User %d requested reboot.', update.effective_user.id)
        yes_no_buttons = [
            [telegram.InlineKeyboardButton('Confirm', callback_data='confirm_reboot'),
             telegram.InlineKeyboardButton('Abort', callback_data='abort_reboot'), ],
        ]
        bot.send_message(chat_id=update.message.chat_id,
                         text='Please confirm reboot',
                         reply_markup=telegram.InlineKeyboardMarkup(yes_no_buttons))

    else:
        unknown(bot, update)


def button(bot, update):
    callback_data = update.callback_query.data

    bot.delete_message(chat_id=update.callback_query.message.chat_id,
                       message_id=update.callback_query.message.message_id)

    if callback_data == 'confirm_shutdown':
        logging.info('User %d confirmed shutdown.', update.effective_user.id)
        os.system('/usr/bin/sudo shutdown -h now')
    elif callback_data == 'abort_shutdown':
        logging.info('User %d aborted shutdown.', update.effective_user.id)
    elif callback_data == 'confirm_reboot':
        os.system('/usr/bin/sudo reboot')
        logging.info('User %d confirmed reboot.', update.effective_user.id)
    elif callback_data == 'abort_reboot':
        logging.info('User %d aborted reboot.', update.effective_user.id)


def unknown(bot, update):
    bot.send_message(chat_id=update.message.chat_id,
                     text="Sorry, I didn't understand that command.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start Telegram Bot for Babyphone.')
    parser.add_argument('--pin',
                        type=int,
                        required=True,
                        help='PIN (integer) for authenticating telegram chat')

    args = parser.parse_args()
    pin = args.pin
    logging.info('PIN: %d', pin)

    updater = Updater(token=read_telegram_token())
    dispatcher = updater.dispatcher

    start_handler = CommandHandler('start',
                                   lambda bot, update, args: start(bot, update, args, pin=pin),
                                   pass_args=True)
    dispatcher.add_handler(start_handler)

    help_handler = CommandHandler('help', usage, pass_args=False)
    dispatcher.add_handler(help_handler)

    default_callback_handler = MessageHandler(known_cmd_filter, default_callback)
    dispatcher.add_handler(default_callback_handler)

    button_handler = CallbackQueryHandler(button)
    dispatcher.add_handler(button_handler)

    unknown_handler = MessageHandler(Filters.command, unknown)
    dispatcher.add_handler(unknown_handler)

    updater.start_polling()
