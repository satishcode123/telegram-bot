import os
import logging
from flask import Flask, request
import telebot
from telebot import types
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
from datetime import datetime
import re
from unidecode import unidecode

# Telegram bot token
BOT_TOKEN = os.getenv("7820183681:AAGtMLIZs64jjOpJOphj9Sz-Cf_B3AoWR5E")
bot = telebot.TeleBot(BOT_TOKEN)

# Paths to the images
top_img = "first.png"  # Transparent base image filename
default_user_image = "default_user_image.png"
default_group_image = "default_group_image.png"
final_image_path = "final_image.png"  # Output image filename
font_path = "Delicious.ttf"  # Path to your font file

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_to_simple_text(text):
    text = unidecode(text)
    text = re.sub(r'[^\x00-\x7F]+', '', text)  # Remove non-ASCII characters
    text = " ".join(text.split())  # Remove extra spaces
    return text

def truncate_text(text, max_length):
    result = ''
    current_length = 0
    for char in text:
        if current_length + len(char.encode('utf-16-le')) // 2 > max_length:
            break
        result += char
        current_length += len(char.encode('utf-16-le')) // 2
    return result

def fetch_image(url, default_image):
    try:
        response = requests.get(url)
        return Image.open(BytesIO(response.content)).convert("RGBA")
    except (requests.exceptions.RequestException, IOError) as e:
        logger.error(f"Error fetching image from URL: {url}. Using default image. Error: {e}")
        return Image.open(default_image)

def create_image(user_image_url, channel_img_url, channel_name, user_name):
    try:
        user_name = convert_to_simple_text(user_name)
        channel_name = convert_to_simple_text(channel_name)

        base_image = Image.open(top_img).convert("RGBA")
        foreground_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))

        user_image_2 = fetch_image(user_image_url, default_user_image)
        user_image_1 = fetch_image(channel_img_url, default_group_image)

        user_image_2 = user_image_2.resize((350, 350))
        user_image_1 = user_image_1.resize((350, 350))

        user_image_coords_1 = (220, 140)
        user_image_coords_2 = (720, 140)

        mask = Image.new("L", user_image_1.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, 350, 350), fill=255)

        circular_user_image_1 = Image.new("RGBA", user_image_1.size)
        circular_user_image_1.paste(user_image_1, (0, 0), mask)
        circular_user_image_2 = Image.new("RGBA", user_image_2.size)
        circular_user_image_2.paste(user_image_2, (0, 0), mask)

        foreground_layer.paste(circular_user_image_1, user_image_coords_1, mask=circular_user_image_1)
        foreground_layer.paste(circular_user_image_2, user_image_coords_2, mask=circular_user_image_2)

        text_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_layer)
        font = ImageFont.truetype(font_path, 45)

        user_name_1 = truncate_text(user_name, 11)
        bbox_1 = draw.textbbox((0, 0), user_name_1, font=font)
        text_width_1 = bbox_1[2] - bbox_1[0]
        center_x_1 = base_image.width // 1.42
        start_x_1 = center_x_1 - (text_width_1 // 2)
        text_coords_1 = (start_x_1, 425)
        draw.text(text_coords_1, user_name_1, font=font, fill=(248, 194, 244))

        user_name_2 = truncate_text(channel_name, 11)
        bbox_2 = draw.textbbox((0, 0), user_name_2, font=font)
        text_width_2 = bbox_2[2] - bbox_2[0]
        center_x_2 = base_image.width // 3.2
        start_x_2 = center_x_2 - (text_width_2 // 2)
        text_coords_2 = (start_x_2, 425)
        draw.text(text_coords_2, user_name_2, font=font, fill=(255, 230, 53))

        final_image = Image.alpha_composite(base_image, text_layer)
        final_image = Image.alpha_composite(foreground_layer, final_image)

        final_image.save(final_image_path)
        return final_image_path
    except Exception as e:
        logger.error(f"Error creating image: {e}")
        return None

@app.route('/' + BOT_TOKEN, methods=['POST'])
def receive_update():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '!', 200

@bot.message_handler(content_types=["new_chat_members"])
def welcome_new_member(message):
    for new_member in message.new_chat_members:
        try:
            user_id = new_member.id
            user_name = new_member.first_name or "User"
            username = new_member.username or "No Username"
            join_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            try:
                photos = bot.get_user_profile_photos(user_id)
                if photos.photos:
                    file_id = photos.photos[0][0].file_id
                    file_info = bot.get_file(file_id)
                    user_image_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
                else:
                    user_image_url = default_user_image
            except Exception as e:
                logger.error(f"Error fetching user profile photo: {e}")
                user_image_url = default_user_image

            group_name = message.chat.title

            try:
                chat_info = bot.get_chat(message.chat.id)
                if chat_info.photo:
                    file_id = chat_info.photo.big_file_id
                    file_info = bot.get_file(file_id)
                    group_image_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
                else:
                    group_image_url = default_group_image
            except Exception as e:
                logger.error(f"Error fetching group photo: {e}")
                group_image_url = default_group_image

            image_path = create_image(user_image_url, group_image_url, group_name, user_name)

            if image_path:
                caption = (
                    f"ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ {group_name}\n\n"
                    f"*ɴᴀᴍᴇ:* {user_name}\n"
                    f"*ᴜꜱᴇʀ ɪᴅ:* {user_id}\n"
                    f"*ᴜꜱᴇʀɴᴀᴍᴇ:* @{username}\n"
                    f"*ᴍᴇɴᴛɪᴏɴ:* [ᴏᴘᴇɴ ᴘʀᴏғɪʟᴇ](tg://user?id={user_id})\n"
                    f"*ᴊᴏɪɴᴇᴅ ᴀᴛ:* {join_time}\n"
                )

                try:
                    bot.send_photo(message.chat.id, open(image_path, "rb"), caption=caption, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Error sending photo: {e}")
            else:
                bot.send_message(message.chat.id, "Welcome to the group!", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error in welcome_new_member handler: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
