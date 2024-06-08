import json
import requests


class SlackClient:
    def __init__(self, token: str, channel: str) -> None:
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        self.url = "https://slack.com/api/chat.postMessage"
        self.channel = channel

    def _send(self, payload: dict):
        response = requests.post(self.url, headers=self.headers, data=json.dumps(payload))

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


if __name__ == "__main__":
    raise RuntimeError("This is module is not executable")
