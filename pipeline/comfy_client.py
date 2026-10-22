"""Klijent za ComfyUI HTTP API: slanje workflow-a, čekanje i preuzimanje rezultata."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

import requests


class ComfyError(RuntimeError):
    pass


class ComfyClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client_id = uuid.uuid4().hex

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def system_stats(self) -> dict[str, Any]:
        """Proverava da li ComfyUI radi i vraća podatke o GPU-u i memoriji."""
        try:
            r = requests.get(self._url("/system_stats"), timeout=self.timeout)
        except requests.ConnectionError as e:
            raise ComfyError(f"ComfyUI ne odgovara na {self.base_url}; da li je pokrenut?") from e
        r.raise_for_status()
        return r.json()

    def upload(self, path: Path, subfolder: str = "flick") -> str:
        """Šalje sliku, zvuk ili video u ComfyUI input folder i vraća ime koje workflow koristi."""
        path = Path(path)
        with path.open("rb") as f:
            r = requests.post(
                self._url("/upload/image"),
                files={"image": (path.name, f)},
                data={"overwrite": "true", "type": "input", "subfolder": subfolder},
                timeout=max(self.timeout, 120),
            )
        if r.status_code != 200:
            raise ComfyError(f"upload {path.name} nije uspeo: {r.status_code} {r.text[:300]}")
        info = r.json()
        sub = info.get("subfolder") or ""
        return f"{sub}/{info['name']}" if sub else info["name"]

    def queue(self, workflow: dict[str, Any]) -> str:
        r = requests.post(
            self._url("/prompt"),
            json={"prompt": workflow, "client_id": self.client_id},
            timeout=self.timeout,
        )
        if r.status_code != 200:
            raise ComfyError(f"ComfyUI je odbio workflow: {r.status_code} {r.text[:2000]}")
        body = r.json()
        if body.get("node_errors"):
            raise ComfyError(f"greške u čvorovima: {body['node_errors']}")
        return body["prompt_id"]

    def wait(self, prompt_id: str, timeout: float = 3600, poll: float = 2.0) -> dict[str, Any]:
        """Čeka da se posao završi; vraća unos iz /history."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            r = requests.get(self._url(f"/history/{prompt_id}"), timeout=self.timeout)
            r.raise_for_status()
            entry = r.json().get(prompt_id)
            if entry:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise ComfyError(f"posao {prompt_id} je pao: {_error_message(status)}")
                if status.get("completed", True):
                    return entry
            time.sleep(poll)
        raise ComfyError(f"posao {prompt_id} nije završen za {timeout:.0f} s")

    @staticmethod
    def output_files(entry: dict[str, Any], node_id: str | None = None) -> list[dict[str, str]]:
        """Svi izlazni fajlovi iz unosa istorije (slike, video, zvuk), opciono samo iz jednog čvora."""
        files: list[dict[str, str]] = []
        for nid, out in entry.get("outputs", {}).items():
            if node_id is not None and str(nid) != str(node_id):
                continue
            for items in out.values():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if isinstance(item, dict) and "filename" in item and item.get("type", "output") == "output":
                        files.append(item)
        return files

    def download(self, item: dict[str, str], dest_dir: Path) -> Path:
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        params = {"filename": item["filename"], "subfolder": item.get("subfolder", ""), "type": item.get("type", "output")}
        r = requests.get(self._url("/view"), params=params, timeout=max(self.timeout, 300), stream=True)
        r.raise_for_status()
        dest = dest_dir / item["filename"]
        with dest.open("wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        return dest

    def run(self, workflow: dict[str, Any], dest_dir: Path, output_node: str | None = None,
            timeout: float = 3600) -> tuple[list[Path], float]:
        """Pošalje workflow, sačeka ga i preuzme izlaze. Vraća (fajlovi, trajanje u sekundama)."""
        start = time.monotonic()
        prompt_id = self.queue(workflow)
        entry = self.wait(prompt_id, timeout=timeout)
        items = self.output_files(entry, output_node)
        if not items:
            raise ComfyError(f"posao {prompt_id} nije dao izlazne fajlove (output_node={output_node})")
        paths = [self.download(item, dest_dir) for item in items]
        return paths, time.monotonic() - start


def _error_message(status: dict[str, Any]) -> str:
    for kind, data in status.get("messages", []):
        if kind == "execution_error":
            return f"{data.get('node_type')} ({data.get('node_id')}): {data.get('exception_message', '').strip()}"
    return "nepoznata greška"
