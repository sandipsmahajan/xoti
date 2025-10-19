# server.py
import datetime
import os
import uuid

from livekit import api
from flask import Flask

app = Flask(__name__)


@app.route('/token/<name>/<room>')
def get_token(name, room):
    token = api.AccessToken(os.getenv('LIVEKIT_API_KEY'), os.getenv('LIVEKIT_API_SECRET')) \
        .with_identity(str(uuid.uuid4())) \
        .with_name(name) \
        .with_ttl(datetime.timedelta(days=30)) \
        .with_grants(api.VideoGrants(
        room_join=True,
        room=room,
    ))
    return token.to_jwt()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
