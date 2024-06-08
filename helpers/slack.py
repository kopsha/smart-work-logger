import json

import requests


def send_slack_message(token, channel, text):
    url = "https://slack.com/api/chat.postMessage"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"channel": channel, "text": text}

    response = requests.post(url, headers=headers, data=json.dumps(payload))

    if response.status_code == 200:
        response_data = response.json()
        if response_data.get("ok"):
            print("Message sent successfully")
        else:
            print(f"Error sending message: {response_data.get('error')}")
    else:
        print(f"Request failed with status code: {response.status_code}")


if __name__ == "__main__":
    raise RuntimeError("This is module is not executable")
