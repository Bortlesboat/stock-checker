import os
import json

CONFIG_DIR = os.path.join(os.environ["USERPROFILE"], "CartBotProfiles")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


class ConfigManager:
    def __init__(self):
        self.config_dir = CONFIG_DIR
        self.config_file = CONFIG_FILE

    def load(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, "r") as f:
                return json.load(f)
        return {}

    def save(self, data):
        """Save config dict. Preserves saved_urls from existing config."""
        os.makedirs(self.config_dir, exist_ok=True)
        existing = self.load()
        data["saved_urls"] = existing.get("saved_urls", {})
        with open(self.config_file, "w") as f:
            json.dump(data, f)

    def get_saved_urls(self):
        return self.load().get("saved_urls", {})

    def save_url_to_library(self, name, urls):
        os.makedirs(self.config_dir, exist_ok=True)
        config = self.load()
        if "saved_urls" not in config:
            config["saved_urls"] = {}
        config["saved_urls"][name] = urls
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)
        print(f"Saved '{name}' to library ({len(urls)} chars)")

    def delete_url_from_library(self, name):
        if not os.path.exists(self.config_file):
            return
        config = self.load()
        config.get("saved_urls", {}).pop(name, None)
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)
        print(f"Deleted '{name}' from library")
