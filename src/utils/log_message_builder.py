from quart import request
from user_agents import parse

async def build_log_message(action: str) -> str:
    ua_string = request.headers.get("User-Agent", "Unknown device")
    user_agent = parse(ua_string)

    device_family = user_agent.device.family
    os_family = user_agent.os.family
    browser_family = user_agent.browser.family

    device_info = f"{device_family} / {os_family} / {browser_family}"

    return f"{action} via {device_info}"
