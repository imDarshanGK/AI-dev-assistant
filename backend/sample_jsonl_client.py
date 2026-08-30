import json

import httpx

SAMPLE_CODE = """
def divide(a, b):
    return a / b

result = divide(10, 0)
password = "example_password"

try:
    pass
except:
    pass
"""

url = "http://localhost:8000/export/jsonl"
payload = {"code": SAMPLE_CODE}


def main():
    with httpx.stream("POST", url, json=payload, timeout=30) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.strip():
                obj = json.loads(line)
                print(f"[{obj['type']}]")
                print(json.dumps(obj["data"], indent=2))
                print()


if __name__ == "__main__":
    main()
