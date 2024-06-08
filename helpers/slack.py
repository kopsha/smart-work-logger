import json
import requests


class SlackClient:
    def __init__(self, token: str, channel: str) -> None:
        self.headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        }
        self.url = "https://slack.com/api/chat.postMessage"
        self.channel = channel

    def _send(self, payload: dict):
        response = requests.post(
            self.url, headers=self.headers, data=json.dumps(payload)
        )

        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("ok"):
                print("Message sent successfully")
            else:
                print(f"Error sending message: {response_data.get('error')}")
        else:
            print(f"Request failed with status code: {response.status_code}")

    def send_message(self, text: str):
        payload = {"channel": self.channel, "text": text}
        self._send(payload)

    def send_blocks(self, blocks: list[str]):
        payload = {"channel": self.channel, "blocks": blocks}
        self._send(payload)

    def upload_image(self, title: str, file_path: str):
        with open(file_path, "rb") as file:
            file_content = file.read()

        payload = dict(filename=file_path, length=len(file_content))
        response = requests.get(
            "https://slack.com/api/files.getUploadURLExternal",
            headers=self.headers,
            params=payload,
        )
        if response.status_code != 200:
            raise RuntimeError("Cannot get upload url, reason", response.text)
        upload_reply = response.json()
        if not upload_reply.get("ok"):
            raise RuntimeError("Failed to get upload url, reason", upload_reply)

        response = requests.post(
            upload_reply.get("upload_url"),
            headers=self.headers,
            files=dict(file=(file_path, file_content, "image/png")),
        )
        if response.status_code != 200:
            raise RuntimeError(
                "Image content upload has failed, reason:", response.text
            )
        else:
            print("Image content uploaded successfully.")

        payload = dict(
            files=[dict(id=upload_reply["file_id"], title=title)],
            channel_id=self.channel,
            initial_comment="initial",
        )
        response = requests.post(
            "https://slack.com/api/files.completeUploadExternal",
            headers=self.headers,
            data=json.dumps(payload),
        )
        print(response.json())


if __name__ == "__main__":
    raise RuntimeError("This is module is not executable")
