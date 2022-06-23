import logging
import os
import re

import redis
from environs import Env
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Filters, Updater
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler

from moltin_api import SimpleMoltinApiClient
from tg_log_handler import TelegramLogHandler


START, HANDLE_MENU, HANDLE_DESCRIPTION, HANDLE_CART, HANDLE_EMAIL = range(5)

log = logging.getLogger(__file__)
_database = None
_moltin_api = None


def on_error(update, context):
    log.exception('An exception occured while handling an event.')


def start(update, context):
    text = (
        "Welcome to out humble fish market.\n"
        "What product are you interested in?"
    )

    product_keyboard = [
        [InlineKeyboardButton(product_name, callback_data=product_id)]
        for product_name, product_id 
        in get_moltin_client().get_products().items()
    ]

    update.message.reply_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(product_keyboard)
    )

    return HANDLE_MENU


def handle_menu(update, context):
    if not update.callback_query:
        return HANDLE_MENU

    users_reply = update.callback_query.data
    update.callback_query.delete_message()

    product_info = get_moltin_client().get_product_by_id(users_reply)
    image_url = get_moltin_client().get_image_url_by_file_id(
        product_info["relationships"]["main_image"]["data"]["id"]
    )

    text = (
        f"{product_info['name']}\n\n"
        f"{product_info['meta']['display_price']['with_tax']['formatted']} per kg\n"
        f"{product_info['meta']['stock']['level']} kg in stock"
    )

    options_keyboard = [
        [
            InlineKeyboardButton("1 kg", callback_data=f"{product_info['id']}:1"),
            InlineKeyboardButton("5 kg", callback_data=f"{product_info['id']}:5"),
            InlineKeyboardButton("10 kg", callback_data=f"{product_info['id']}:10")
        ],
        [InlineKeyboardButton("Back", callback_data="return")],
        [InlineKeyboardButton("Cart", callback_data="cart")]
    ]

    update.callback_query.message.reply_photo(
        image_url,
        caption=text,
        reply_markup=InlineKeyboardMarkup(options_keyboard)
    )

    return HANDLE_DESCRIPTION


def get_text_and_buttons_for_cart(cart_id):
    cart_items, full_price = get_moltin_client().get_cart_and_full_price(cart_id)
    cart_items_display = [
        f"{item['name']}\n"
        f"{item['meta']['display_price']['with_tax']['unit']['formatted']} per kg\n"
        f"{item['quantity']}kg for "
        f"{item['meta']['display_price']['with_tax']['value']['formatted']}"
        for item in cart_items
    ]
    cart_items_display.append(
        f"Total price: {full_price}"
    )

    text = (
        "\n\n".join(cart_items_display)
        if cart_items else
        "Cart is empty. Go on and throw in some stuff :D"
    )

    cart_keyboard = [
        [InlineKeyboardButton(f"Remove {item['name']}", callback_data=item["id"])]
        for item in cart_items 
    ]
    cart_keyboard.append(
        [InlineKeyboardButton(f"Back", callback_data="return")]
    )
    if cart_items:
        cart_keyboard.append(
            [InlineKeyboardButton(f"Checkout", callback_data="checkout")]
        )

    return text, cart_keyboard


def handle_description(update, context):
    if not update.callback_query:
        return HANDLE_DESCRIPTION

    users_reply = update.callback_query.data
    if users_reply == "cart":
        update.callback_query.edit_message_reply_markup(reply_markup=None)
        
        text, cart_keyboard = get_text_and_buttons_for_cart(update.effective_chat.id)

        update.callback_query.message.reply_text(
            text=text,
            reply_markup = InlineKeyboardMarkup(cart_keyboard)
        )
        return HANDLE_CART

    if users_reply == "return":
        update.callback_query.edit_message_reply_markup(reply_markup=None)

        product_keyboard = [
            [InlineKeyboardButton(product_name, callback_data=product_id)]
            for product_name, product_id 
            in get_moltin_client().get_products().items()
        ]

        update.callback_query.message.reply_text(
            text="What product are you interested in?",
            reply_markup=InlineKeyboardMarkup(product_keyboard)
        )
        return HANDLE_MENU
    
    product_id, quantity = users_reply.split(":")
    get_moltin_client().add_product_to_cart(
        cart_id=update.effective_chat.id,
        product_id=product_id,
        quantity=int(quantity)
    )
    update.callback_query.answer(text="Item added to the cart")

    return HANDLE_DESCRIPTION


def handle_cart(update, context):
    if not update.callback_query:
        return HANDLE_CART

    users_reply = update.callback_query.data

    if users_reply == "return":
        update.callback_query.edit_message_reply_markup(reply_markup=None)

        product_keyboard = [
            [InlineKeyboardButton(product_name, callback_data=product_id)]
            for product_name, product_id 
            in get_moltin_client().get_products().items()
        ]

        update.callback_query.message.reply_text(
            text="What product are you interested in?",
            reply_markup=InlineKeyboardMarkup(product_keyboard)
        )

        return HANDLE_MENU
    
    if users_reply == "checkout":
        update.callback_query.edit_message_reply_markup(reply_markup=None)

        text = (
            "To complete your order please enter your email address.\n"
            "Our commercial department will issue the payment."
        )

        update.callback_query.message.reply_text(
            text=text,
        )
        return HANDLE_EMAIL

    get_moltin_client().remove_product_from_cart(
        cart_id=update.effective_chat.id,
        item_id=users_reply
    )

    text, cart_keyboard = get_text_and_buttons_for_cart(update.effective_chat.id)

    update.callback_query.answer(text="Item removed from the cart")
    update.callback_query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(cart_keyboard)
    )

    return HANDLE_CART


def handle_email(update, context):
    user_reply = update.message.text
    if not re.match(r'^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w{2,3}$', user_reply.lower()):
        update.message.reply_text(
            text="Your email look kinda messed. Please try again.",
        )
        return HANDLE_EMAIL
    
    customer_id = get_moltin_client().get_or_create_customer_by_email(user_reply)
    get_moltin_client().checkout(update.effective_chat.id, customer_id)
    get_moltin_client().empty_cart(update.effective_chat.id)

    update.message.reply_text(
        text="Thank you for your order! We will contact you at once :D",
    )

    return START


def handle_users_reply(update, context):
    """Handle by state machine"""

    db = get_database_connection()
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = START
    else:
        user_state = int(db.get(chat_id))
    
    states_functions = {
        START: start,
        HANDLE_MENU: handle_menu,
        HANDLE_DESCRIPTION: handle_description,
        HANDLE_CART: handle_cart,
        HANDLE_EMAIL: handle_email,
    }
    state_handler = states_functions[user_state]

    next_state = state_handler(update, context)
    db.set(chat_id, next_state)


def get_database_connection():
    """Create or retrive connection to redis database"""
    global _database
    if _database is None:
        database_password = os.getenv("DATABASE_PASSWORD")
        database_host = os.getenv("DATABASE_HOST")
        database_port = os.getenv("DATABASE_PORT")

        _database = redis.Redis(
            host=database_host, 
            port=database_port, 
            password=database_password, 
            decode_responses=True
        )

    return _database


def get_moltin_client():
    """Get or create instance of Moltin API Client to maintain access token"""
    global _moltin_api
    if _moltin_api is None:
        client_id = os.getenv("CLIENT_ID")
        client_secret = os.getenv("CLIENT_SECRET")
        _moltin_api = SimpleMoltinApiClient(client_id, client_secret)

    return _moltin_api


if __name__ == '__main__':
    env = Env()
    env.read_env()
    
    logging.basicConfig(level=logging.WARNING)
    log.setLevel(logging.ERROR)
    log.addHandler(
        TelegramLogHandler(env('ALARM_BOT_TOKEN'), env('ALARM_CHAT_ID'))
    )

    token = env("BOT_TOKEN")
    updater = Updater(token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    dispatcher.add_error_handler(on_error)
    updater.start_polling()
    updater.idle()