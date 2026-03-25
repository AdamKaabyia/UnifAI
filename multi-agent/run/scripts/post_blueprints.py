import argparse
import requests
from pathlib import Path


def post_yaml(file_path: Path, api_url: str):
    try:
        with file_path.open("r", encoding="utf-8") as f:
            yaml_data = f.read()

        response = requests.post(api_url, data=yaml_data, headers={"Content-Type": "application/x-yaml"})

        print(f"[{file_path.name}] Status Code:", response.status_code)
        try:
            print("Response:", response.json())
        except Exception:
            print("Raw Response:", response.text)

    except Exception as e:
        print(f"[{file_path.name}] Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Upload YAML blueprints to /blueprint.save endpoint")
    parser.add_argument("--host", required=True, help="Host of the API, e.g. 10.46.254.131")
    parser.add_argument("--port", required=True, type=int, help="Port of the API, e.g. 8002")
    parser.add_argument("--files", required=True, nargs="+", help="List of YAML file paths to upload")

    args = parser.parse_args()

    api_url = f"http://{args.host}:{args.port}/api/blueprints/blueprint.save"

    for file_path_str in args.files:
        path = Path(file_path_str)
        if not path.exists():
            print(f"[{path.name}] File not found. Skipping.")
            continue
        post_yaml(path, api_url)


if __name__ == "__main__":
    main()
