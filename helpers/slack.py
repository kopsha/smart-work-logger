import ssl

import certifi
from slack_sdk.errors import SlackApiError
from slack_sdk.web import WebClient


class SlackClient:
    def __init__(self, token: str, channel: str) -> None:
        self.channel = channel
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.client = WebClient(token=token, ssl=ssl_context)

    def send_message(self, text: str):
        try:
            self.client.chat_postMessage(channel=self.channel, text=text)
        except SlackApiError as err:
            print("Cannot send message, reason:", err.response["error"])
            print(err)

    def upload_image(self, intro: str, file_path: str):
        try:
            self.client.files_upload_v2(
                channel=self.channel,
                file=file_path,
                title=file_path.rstrip(".png").replace("_", " "),
                initial_comment=intro,
            )
        except SlackApiError as err:
            print("Cannot upload image, reason", err)
            print(err.response)


if __name__ == "__main__":
    raise RuntimeError("This is module is not executable")
