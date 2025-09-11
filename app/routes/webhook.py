from flask import Blueprint, request, current_app
from telegram import Update

webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(), current_app.bot)
    current_app.dispatcher.process_update(update)
    return '', 200