import logging
import datetime
import os
import sys
import io
import time
from pprint import pformat, pprint

from flask import Flask, render_template, jsonify, request, abort

import segno
from PIL import Image, ImageFont, ImageDraw

from werkzeug.exceptions import BadRequest

app = Flask(__name__)
version = "0.1.0"
RaspPI = False
libdir = ""

# ERROR_CORRECTION = "H"  # can be "l", "M", "Q", "H" (7%, 15%, 25%, 30%=highest correction level)

# display wider side x narrower side in pixel / mm.
# set display specific settings after posix is identied
display_dimensions_pixels = (0, 0)
display_dimensions_mm = (0, 0)

# possible settings: 1.54, 2.9
# connected_display_type = "2.9"
connected_display_type = "1.54"

if os.name == 'posix':
    libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'waveshare')
    if os.path.exists(libdir):
        sys.path.append(libdir)
    if connected_display_type == "1.54":
        from waveshare import epd1in54 as display

        display_dimensions_mm = (27.60, 27.60)
        display_dimensions_pixels = (200, 200)
        font_boot_screen = ImageFont.truetype(os.path.join(libdir, 'Font.ttc'), 22)

    elif connected_display_type == "2.9":
        from waveshare import epd2in9 as display

        display_dimensions_mm = (66.89, 29.05)
        display_dimensions_pixels = (296, 128)
        font_boot_screen = ImageFont.truetype(os.path.join(libdir, 'Font.ttc'), 18)

    RaspPI = True

    fonts = {}

    for c in range(16, 32, 2):
        fonts[c] = ImageFont.truetype(os.path.join(libdir, 'Font.ttc'), c)

    print("posix detected")

one_mm_wider = display_dimensions_pixels[0] / display_dimensions_mm[0]
one_cm_wider = round(one_mm_wider * 10)
one_mm_smaller = display_dimensions_pixels[1] / display_dimensions_mm[1]
one_cm_smaller = round(one_mm_smaller * 10)


def get_ip_addresses(must_include='192.168', debug_log=False):
    addresses = []
    try:
        try:
            import netifaces
        except BaseException as e:
            logging.info(f"kioskstdlib.get_ip_addresses: netifaces module not installed.")
            return []

        if debug_log:
            logging.debug(f"get_ip_addresses: Searching network interfaces ...")
        for dev in netifaces.interfaces():
            try:
                if debug_log:
                    logging.debug(f"get_ip_addresses: Found device {pformat(dev)}:")
                address = netifaces.ifaddresses(dev)[netifaces.AF_INET]
                if debug_log:
                    if address:
                        logging.debug(f"                  {pformat(address)}")
                    else:
                        logging.debug(f"                  No information available.")
                for part in address:
                    if 'addr' in part:
                        if must_include and (part['addr'].find(must_include) > -1):
                            addresses.append(part['addr'])
            except BaseException as e:
                if debug_log:
                    if "KeyError(2)" in repr(e):
                        logging.debug(f"                  Device has no IP addresses")
                    else:
                        logging.debug(f"                  Could not get more information: {repr(e)} ")
    except BaseException as e:
        logging.error(f"kioskstdlib.get_ip_addresses: {repr(e)}")

    if debug_log:
        logging.debug(f"get_ip_addresses: {len(addresses)} network addresses found.")

    return addresses


with app.app_context():
    addresses = get_ip_addresses()
    if RaspPI and libdir:
        epd = display.EPD()
        print(f"display dimensions: {epd.width}x{epd.height}")
        logging.info("init and Clear")
        epd.init(epd.lut_full_update)
        epd.Clear(0xFF)
        time.sleep(1)
        logging.info(f"lib is {libdir}")
        if epd.width == epd.height:
            image = Image.new('1', (epd.width, epd.height), 255)  # 255: clear the frame
        else:
            image = Image.new('1', (epd.height, epd.width), 255)  # 255: clear the frame

        draw = ImageDraw.Draw(image)

        # draw.rectangle((0, 10, 200, 34), fill=0)
        line_height = font_boot_screen.size
        draw.text((8, line_height), f"Kiosk e-Ink Server", font=font_boot_screen, fill=0)
        draw.text((8, line_height * 2), f"running on IP", font=font_boot_screen, fill=0)

        line = line_height * 3
        for address in addresses:
            draw.text((8, line), f"{address}", font=font_boot_screen, fill=0)
            line += line_height

        line += int(line_height / 2)
        draw.text((8, line), f"{epd.width} x {epd.height} detected", font=font_boot_screen, fill=0)
        line += line_height
        draw.text((8, line), datetime.datetime.now().strftime("%a, %H:%M:%S"), font=font_boot_screen, fill=0)
        if epd.width == epd.height:
            epd.display(epd.getbuffer(image.rotate(270)))
        else:
            epd.display(epd.getbuffer(image.rotate(180)))

        time.sleep(2)
        epd.sleep()


@app.route("/")
def index():
    return render_template("index.html", version=version)


@app.route("/version")
def version_route():
    response = jsonify({
        "app": "Kiosk E-Ink Display Server",
        "version": version
    })
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


def draw_label(canvas, labels, x, y, font):
    for c, label in enumerate(labels):
        label = label.strip('\n\r')
        canvas.text((x, y + c * font.size), f"{label}",
                    font=font, fill=0)


def draw_scale(scale_panel, x, y, scale_height, width_cm=2):
    scale_panel.rectangle((x, y,
                           x + width_cm * one_cm_wider, y + scale_height), outline=0, fill=255, width=2)

    for n in range(0, width_cm * 10, 2):
        scale_panel.rectangle((x + n * one_mm_wider, y,
                               x + (n + 1) * one_mm_wider, y + scale_height / 2), outline=0, width=1,
                              fill=0)

    scale_panel.rectangle((x, y + scale_height / 2,
                           x + width_cm * one_cm_wider, y + scale_height), outline=0, fill=255, width=2)

    for n in range(0, int(width_cm * 10 / 2), 10):
        scale_panel.rectangle((x + n * one_mm_wider, y + scale_height / 2,
                               x + (n + 5) * one_mm_wider, y + scale_height), outline=0, fill=0)

    for n in range(0, int(width_cm * 10 / 2), 20):
        scale_panel.rectangle((x + int(width_cm / 2) * one_cm_wider + n * one_mm_wider, y + scale_height / 2,
                               x + int(width_cm / 2) * one_cm_wider + (n + 10) * one_mm_wider, y + scale_height),
                              outline=0, fill=0)

    # scale_panel.rectangle((x + int(width_cm / 2) * one_cm_wider, y + scale_height / 2,
    #                        x + one_cm_wider * width_cm, y + scale_height), outline=0, fill=0, width=2)


def show_on_square_display(data, font_size, labels, scale_type):
    img_out = None
    img_qr_code = None
    try:
        qrcode = segno.make(data, micro=False)  # , error="H")
        qrcode_size = qrcode.symbol_size()[0]
        scale = round(
            (epd.width - (one_cm_wider * 1.5)) / qrcode_size
        )

        if font_size == "auto":
            font_size = 22
        else:
            font_size = int(font_size)

        if font_size in fonts:
            font_label = fonts[font_size]
        else:
            if font_size > 0:
                raise Exception(f'Font size {font_size} not available.')
            else:
                font_label = None

        print(f"qrcode size is {qrcode.symbol_size()}")
        if font_label:
            print(f"font_size is {font_label.size}")
        else:
            print(f"font_size is 0: No identifier.")

        print(f"scale is {scale}")

        out = io.BytesIO()
        qrcode.save(out, scale=scale, border=0, kind='png')
        out.seek(0)
        img_qr_code = Image.open(out)
        epd.init(epd.lut_full_update)
        epd.Clear(0xFF)
        img_out = Image.new('1', (epd.width, epd.height), 255)  # 255: clear the frame

        margin = 3

        canvas = ImageDraw.Draw(img_out)
        display_height = epd.height

        if scale_type.lower() != "none":
            if font_label:
                draw_label(canvas, labels, margin, margin + margin + one_cm_wider * 2, font_label)
            img_out = img_out.rotate(90)
            scale_panel = ImageDraw.Draw(img_out)
            draw_scale(scale_panel, margin, display_height - margin - one_cm_wider / 2, one_cm_wider / 2)
        else:
            if font_label:
                draw_label(canvas, labels, margin, margin + img_qr_code.size[1] + margin, font_label)


        img_out.paste(img_qr_code, (margin, margin))

        return img_out.rotate(270)
    finally:
        try:
            if img_qr_code:
                img_qr_code.close()
        except:
            pass
        try:
            if img_out:
                img_out.close()
        except:
            pass


def show_on_2_9_display(data, font_size, labels, scale_type, display_type):
    img_out = None
    img_qr_code = None
    orientation = "P" if display_type[-1:] == "P" else "L"
    print(f"orientation is {orientation}")

    qrcode = segno.make(data, micro=False)  # , error="H")
    qrcode_size = qrcode.symbol_size()[0]

    if orientation == "P":
        display_width = display_dimensions_pixels[1]
        display_height = display_dimensions_pixels[0]
    else:
        display_width = display_dimensions_pixels[0]
        display_height = display_dimensions_pixels[1]

    try:
        min_dimension = min(display_width, display_height) - one_cm_wider / 2
        scale = round(
            min_dimension / qrcode_size
        )

        if font_size == "auto":
            font_size = 16
        else:
            font_size = int(font_size)

        if font_size in fonts:
            font_label = fonts[font_size]
        else:
            if font_size > 0:
                raise Exception(f'Font size {font_size} not available.')
            else:
                font_label = None

        print(f"qrcode size is {qrcode.symbol_size()}")
        if font_label:
            print(f"font_size is {font_label.size}")
        else:
            print(f"font_size is 0: No identifier.")

        print(f"scale is {scale}")

        out = io.BytesIO()
        qrcode.save(out, scale=scale, border=0, kind='png')
        out.seek(0)
        img_qr_code = Image.open(out)

        epd.init(epd.lut_full_update)
        epd.Clear(0xFF)

        img_out = Image.new('1', (display_width, display_height), 255)  # 255: clear the frame

        canvas = ImageDraw.Draw(img_out)

        margin = 3

        scale_end = 0
        if scale_type.lower() != "none":
            if orientation == "L":
                draw_scale(canvas, margin, display_height - margin - one_cm_smaller / 2, one_cm_wider / 2, width_cm=6)
            else:
                draw_scale(canvas, margin, margin, one_cm_wider / 2)
                scale_end = margin + one_cm_wider / 2

        if font_label:
            if orientation == "P":
                draw_label(canvas, labels, margin, scale_end + margin + img_qr_code.height, font_label)
            else:
                draw_label(canvas, labels, 2 * margin + img_qr_code.width, margin, font_label)

        if orientation == "L":
            img_out.paste(img_qr_code, (margin, margin))
        else:
            img_out.paste(img_qr_code, (margin, int(margin + scale_end)))

        if orientation == "P":
            return img_out.rotate(0)
        else:

            return img_out.rotate(180)
    finally:
        try:
            if img_qr_code:
                img_qr_code.close()
        except:
            pass
        try:
            if img_out:
                img_out.close()
        except:
            pass


@app.route("/show", methods=['POST'])
def show_qr_code():
    if "data" not in request.form:
        abort(BadRequest.code)

    data = request.form["data"]
    labels = request.form["label"].split("\n")
    display_type = connected_display_type
    font_size = "auto"
    scale_type = "auto"
    try:
        display_type = request.form["display-type"]
        font_size = request.form["font-size"]
        scale_type = request.form["scale-type"]
    except:
        pass

    print(f"display_type: {display_type}, font_size: {font_size}, scale_type: {scale_type}")
    rc = True
    msg = ""
    img = None
    try:
        if not display_type.startswith(connected_display_type):
            raise Exception(f"requested display type {display_type} different from connected {connected_display_type}.")

        if connected_display_type in ["1.54"]:
            img = show_on_square_display(data, font_size, labels, scale_type)
        elif connected_display_type in ["2.9"]:
            img = show_on_2_9_display(data, font_size, labels, scale_type, display_type)

        if img:
            epd.display(epd.getbuffer(img))
        else:
            raise Exception('No image to show.')

    except BaseException as e:
        logging.error(f"show_qr_code: Exception {repr(e)}")
        rc = False
        msg = repr(e)

    response = jsonify({"result": rc,
                        "msg": msg})
    response.headers.add('Access-Control-Allow-Origin', '*')

    return response
