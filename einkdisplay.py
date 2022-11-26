from flask import Flask, render_template, jsonify, request, abort

import segno
import io
from PIL import Image

from werkzeug.exceptions import BadRequest

app = Flask(__name__)
version = "0.1.0"

SCALE = 1
ERROR_CORRECTION = "H"  # can be "l", "M", "Q", "H" (7%, 15%, 25%, 30%=highest correction level)


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
