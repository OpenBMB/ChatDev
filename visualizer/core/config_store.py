# ══════════════════════════════════════════════════════════════
#   config_store.py — 설정 파일 통합 관리 (#7)
#   분산된 .json 설정 파일들의 중앙 관리
# ══════════════════════════════════════════════════════════════

import os
import json
import hashlib
import logging
import threading
import time
from datetime import datetime

logger = logging.getLogger("chatdev.config_store")


class ConfigStore:
    """중앙 설정 저장소: 분산 .json 파일 통합 관리 + 핫 리로드."""

    def __init__(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self._root = root
        self._store = {}
        self._hashes = {}
        self._lock = threading.Lock()
        self._watch_thread = None
        self._watching = False

        # 관리 대상 설정 파일들
        self._config_paths = {
            "api_keys": os.path.join(root, "visualizer", ".api_keys.json"),
            "users": os.path.join(root, "visualizer", ".users.json"),
            "cross_squad": os.path.join(root, "CompanyConfig", "cross_squad_bus.json"),
            "squad_stats": os.path.join(root, "visualizer", "squad_stats.json"),
        }
        self._load_all()

    def _file_hash(self, path):
        if not os.path.exists(path):
            return None
        with open(path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def _load_file(self, name, path):
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._store[name] = data
                self._hashes[name] = self._file_hash(path)
                return True
        except Exception as e:
            logger.warning(f"[ConfigStore] Failed to load {name}: {e}")
        return False

    def _load_all(self):
        with self._lock:
            loaded = 0
            for name, path in self._config_paths.items():
                if self._load_file(name, path):
                    loaded += 1
            logger.info(f"[ConfigStore] Loaded {loaded}/{len(self._config_paths)} configs")

    def get(self, name, default=None):
        """Get a config by name."""
        with self._lock:
            return self._store.get(name, default)

    def set(self, name, data, persist=True):
        """Set a config value."""
        with self._lock:
            self._store[name] = data
            if persist and name in self._config_paths:
                path = self._config_paths[name]
                try:
                    from visualizer.core.atomic_write import atomic_write_json
                    atomic_write_json(path, data)
                except ImportError:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                self._hashes[name] = self._file_hash(path)

    def get_value(self, name, key, default=None):
        """Get a specific key from a config."""
        cfg = self.get(name, {})
        if isinstance(cfg, dict):
            return cfg.get(key, default)
        return default

    def register_path(self, name, path):
        """Register a new config file to manage."""
        self._config_paths[name] = path
        self._load_file(name, path)

    def reload(self, name=None):
        """Reload config(s) from disk."""
        if name:
            path = self._config_paths.get(name)
            if path:
                self._load_file(name, path)
        else:
            self._load_all()

    def check_changes(self):
        """Check for file changes and reload if needed."""
        changed = []
        with self._lock:
            for name, path in self._config_paths.items():
                current_hash = self._file_hash(path)
                if current_hash and current_hash != self._hashes.get(name):
                    self._load_file(name, path)
                    changed.append(name)
        if changed:
            logger.info(f"[ConfigStore] Hot reloaded: {changed}")
        return changed

    def start_watching(self, interval=10):
        """Start background watcher for file changes."""
        if self._watching:
            return
        self._watching = True

        def _loop():
            while self._watching:
                self.check_changes()
                time.sleep(interval)

        self._watch_thread = threading.Thread(target=_loop, daemon=True, name="config-watcher")
        self._watch_thread.start()

    def stop_watching(self):
        self._watching = False

    def list_configs(self):
        """List all managed configs."""
        return {name: {"path": path, "loaded": name in self._store,
                       "hash": self._hashes.get(name)}
                for name, path in self._config_paths.items()}

    def load_team_configs(self):
        """Load all team configs from CompanyConfig/Teams/."""
        teams_dir = os.path.join(self._root, "CompanyConfig", "Teams")
        if not os.path.isdir(teams_dir):
            return {}
        teams = {}
        for team_name in os.listdir(teams_dir):
            team_dir = os.path.join(teams_dir, team_name)
            if not os.path.isdir(team_dir):
                continue
            team = {}
            for fname in os.listdir(team_dir):
                if fname.endswith(".json"):
                    try:
                        with open(os.path.join(team_dir, fname), 'r') as f:
                            team[fname.replace(".json", "")] = json.load(f)
                    except Exception:
                        pass
            teams[team_name] = team
        return teams


# ── Singleton ──
config_store = ConfigStore()
logger.info("✅ [Config Store] Loaded")
