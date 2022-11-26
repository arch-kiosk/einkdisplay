import logging
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

SCALE = 1
ERROR_CORRECTION = "H"  # can be "l", "M", "Q", "H" (7%, 15%, 25%, 30%=highest correction level)

if os.name == 'posix':
    libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'waveshare')
    if os.path.exists(libdir):
        sys.path.append(libdir)
    from waveshare import epd1in54 as display

    RaspPI = True
    print("posix detected")


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
        print("init and Clear")
        epd.init(epd.lut_full_update)
        epd.Clear(0xFF)
        time.sleep(1)
        print(f"lib is {libdir}")
        image = Image.new('1', (epd.width, epd.height), 255)  # 255: clear the frame

        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(os.path.join(libdir, 'Font.ttc'), 22)

        # draw.rectangle((0, 10, 200, 34), fill=0)
        draw.text((8, 12), f"Kiosk e-Ink Server", font=font, fill=0)
        draw.text((8, 36), f"running on IP", font=font, fill=0)

        line = 60
        for address in addresses:
            draw.text((8, line), f"{address}", font=font, fill=0)
            line += 24

        line += 24
        draw.text((8, line), f"{epd.width} x {epd.height} detected", font=font, fill=0)
        epd.display(epd.getbuffer(image.rotate(90)))
        time.sleep(2)
        epd.sleep()


@app.route("/")
def index():
    return render_template("index.html", version=version)


@app.route("/version")
def version_route():
    return {
        "app": "Kiosk E-Ink Display Server",
        "version": version
    }


@app.route("/show", methods=['POST'])
def show_qr_code():
    if "data" not in request.form:
        abort(BadRequest.code)

    data = request.form["data"]
    qrcode = segno.make(data, micro=False, error="H")
    out = io.BytesIO()
    qrcode.save(out, scale=SCALE, kind='png')
    out.seek(0)
    img = Image.open(out)
    img.close()
    return {"result": True,
            "qrcode-format": qrcode.designator}
