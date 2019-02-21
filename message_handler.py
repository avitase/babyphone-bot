import functools
import logging

from telegram.ext import BaseFilter, Filters, Updater, CallbackQueryHandler
from telegram.ext import MessageHandler as TelegramMessageHandler


class CommandFilter(BaseFilter):
    def __init__(self, *cmds):
        self.cmds = cmds

    def unify(cmd):
        return cmd.lower().strip()

    def filter(self, cmd):
        return CommandFilter.unify(cmd.text) in self.cmds


class MessageHandler(object):
    def __init__(self, token, chat_id, commands, queries):
        self.chat_id = chat_id
        self.commands = commands
        self.queries = queries

        def do_nothing(*args, **kwargs):
            pass

        self.callbacks = {cmd: do_nothing for cmd in commands}
        self.query_callbacks = {query: do_nothing for query in queries}

        self._updater = Updater(token=token)
        dispatcher = self._updater.dispatcher

        filter = (Filters.command | Filters.text) & CommandFilter(*commands)
        dispatcher.add_handler(TelegramMessageHandler(filter, self.callback))
        dispatcher.add_handler(TelegramMessageHandler(Filters.command, self.callback_fallback))

        dispatcher.add_handler(CallbackQueryHandler(self.query_callback))

    def callback(self, bot, update):
        msg = update.message

        if msg.chat_id != self.chat_id:
            logging.warning('Unauthorized access denied for user %d.', update.effective_user.id)
            bot.send_message(chat_id=msg.chat_id,
                             text='Sorry, your chat id {} is invalid! '
                                  'This chat is not authorized to use the Babyphone Knecht.'.format(msg.chat_id))
        else:
            cmd = CommandFilter.unify(msg.text)
            self.callbacks[cmd](bot, update)

    def callback_fallback(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id,
                         text="Sorry, I didn't understand that command.")

    def query_callback(self, bot, update):
        if update.callback_query.message.chat_id != self.chat_id:
            logging.warning('Unauthorized query callback')
        else:
            query = CommandFilter.unify(update.callback_query.data)
            self.query_callbacks[query](bot, update)

    def register_callback(self, cmd):
        def wrapper(f):
            self.callbacks[CommandFilter.unify(cmd)] = f
            return f

        return wrapper

    def register_query_callback(self, query, remove_keyboard=True):
        def wrapper(f):
            @functools.wraps(f)
            def wrapped_f(bot, update, *args, **kwargs):
                if remove_keyboard:
                    bot.delete_message(chat_id=update.callback_query.message.chat_id,
                                       message_id=update.callback_query.message.message_id)
                f(bot, update, *args, **kwargs)

            self.query_callbacks[CommandFilter.unify(query)] = wrapped_f
            return f

        return wrapper

    def run(self):
        self._updater.start_polling()
