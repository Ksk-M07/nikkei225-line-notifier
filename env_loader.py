"""
.env を os.environ に読み込む軽量ローダー（外部ライブラリ不要）。

GitHub Actions上では .env が存在しないため何もしない。
既に設定済みの環境変数は上書きしない（CI側のsecretsを優先）。
"""

import os
from pathlib import Path

ENV_PATH = Path(__file__).with_name(".env")


def load_env(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
