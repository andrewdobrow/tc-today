"""Durable article-image mirroring for Treasure Coast Today.

The module is deliberately storage-provider-light.  The persistent registry is keyed
by canonical article slug and records both publisher provenance and the public TCT
mirror.  Bunny Storage is the first backend, but registry field names remain generic
so a future provider migration does not require an editorial data migration.

Modes:
  external - current behavior; no network/storage work.
  shadow   - mirror and verify, but leave reader-facing URLs unchanged.
  mirror   - mirror and verify, then return the TCT-hosted URL. Any failure falls back
             to the original publisher URL.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests

SCHEMA_VERSION = 1
DEFAULT_MAX_IMAGE_BYTES = 25 * 1024 * 1024
_ALLOWED_MODES = {"external", "shadow", "mirror"}
_CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
    "image/tiff": ".tif",
}

_PUBLISHER_NAMES_BY_DOMAIN = {
    "tcpalm.com": "TCPalm",
    "wptv.com": "WPTV",
    "wpbf.com": "WPBF",
    "cbs12.com": "CBS12",
    "sun-sentinel.com": "Sun Sentinel",
    "palmbeachpost.com": "Palm Beach Post",
    "hometownnewstc.com": "Hometown News",
    "wflx.com": "Fox 29",
    "bbci.co.uk": "BBC News",
    "npr.org": "NPR",
    "yahoo.com": "Yahoo News",
    "apnews.com": "AP News",
    "reuters.com": "Reuters",
    "usatoday.com": "USA Today",
    "cnn.com": "CNN",
    "nbcnews.com": "NBC News",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalized_mode(value: str | None = None) -> str:
    mode = str(value if value is not None else os.getenv("TCT_ARTICLE_IMAGE_MODE", "external"))
    mode = mode.strip().lower()
    return mode if mode in _ALLOWED_MODES else "external"


def _clean_host(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    if raw.startswith("https://"):
        raw = raw[8:]
    elif raw.startswith("http://"):
        raw = raw[7:]
    return raw.strip("/")


def _storage_host_from_env() -> str:
    explicit = _clean_host(os.getenv("BUNNY_STORAGE_API_HOST", ""))
    if explicit:
        return explicit
    region = str(os.getenv("BUNNY_STORAGE_REGION", "")).strip().lower()
    if not region or region in {"de", "de-fs", "falkenstein", "germany"}:
        return "storage.bunnycdn.com"
    return f"{region}.storage.bunnycdn.com"


def _infer_source_name(source_url: str) -> str:
    """Return a stable publisher label from a known publisher article URL."""
    try:
        host = urlsplit(str(source_url or "")).netloc.lower().split(":", 1)[0]
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    for domain, name in _PUBLISHER_NAMES_BY_DOMAIN.items():
        if host == domain or host.endswith("." + domain):
            return name
    return ""


def _registry_template() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "storage_provider": "bunny",
        "updated_at": "",
        "articles": {},
        "objects": {},
    }


def _extension_for(content_type: str, source_url: str) -> str:
    kind = str(content_type or "").split(";", 1)[0].strip().lower()
    if kind in _CONTENT_TYPE_EXTENSIONS:
        return _CONTENT_TYPE_EXTENSIONS[kind]
    path_suffix = Path(urlsplit(source_url).path).suffix.lower()
    if path_suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg", ".bmp", ".tif", ".tiff"}:
        return ".jpg" if path_suffix == ".jpeg" else (".tif" if path_suffix == ".tiff" else path_suffix)
    guessed = mimetypes.guess_extension(kind) if kind else None
    if guessed:
        return guessed
    raise ValueError(f"unsupported image content type: {content_type or 'missing'}")


class ArticleImageMirror:
    def __init__(self, root: Path, *, session=None):
        self.root = Path(root)
        self.mode = _normalized_mode()
        self.zone = str(os.getenv("BUNNY_STORAGE_ZONE_NAME", "")).strip()
        self.password = str(os.getenv("BUNNY_STORAGE_ZONE_PASSWORD", "")).strip()
        self.storage_host = _storage_host_from_env()
        self.public_base = str(os.getenv("BUNNY_CDN_BASE_URL", "")).strip().rstrip("/")
        self.max_bytes = int(os.getenv("TCT_ARTICLE_IMAGE_MAX_BYTES", str(DEFAULT_MAX_IMAGE_BYTES)) or DEFAULT_MAX_IMAGE_BYTES)
        self.registry_path = self.root / "data" / "article-image-registry.json"
        self.report_path = self.root / "data" / "article-image-mirror-report.json"
        self.session = session or requests.Session()
        self.started = time.perf_counter()
        self.registry = self._load_registry()
        self.events = []
        self.stats = {
            "candidates": 0,
            "registry_hits": 0,
            "downloads": 0,
            "uploads": 0,
            "hash_dedupe_hits": 0,
            "source_revalidations": 0,
            "source_changes_detected": 0,
            "verified": 0,
            "fallbacks": 0,
            "registry_writes": 0,
            "metadata_repairs": 0,
        }
        self.timing = {
            "candidate_seconds": 0.0,
            "download_seconds": 0.0,
            "upload_seconds": 0.0,
            "verification_seconds": 0.0,
            "revalidation_seconds": 0.0,
            "registry_write_seconds": 0.0,
            "metadata_repair_seconds": 0.0,
        }
        self.config_error = self._configuration_error()
        if self.mode in {"shadow", "mirror"}:
            self._repair_registry_source_names()

    @property
    def enabled(self) -> bool:
        return self.mode in {"shadow", "mirror"} and not self.config_error

    def _configuration_error(self) -> str:
        if self.mode == "external":
            return ""
        missing = []
        if not self.zone:
            missing.append("BUNNY_STORAGE_ZONE_NAME")
        if not self.password:
            missing.append("BUNNY_STORAGE_ZONE_PASSWORD")
        if not self.public_base:
            missing.append("BUNNY_CDN_BASE_URL")
        if not self.storage_host:
            missing.append("BUNNY_STORAGE_API_HOST/BUNNY_STORAGE_REGION")
        return "missing " + ", ".join(missing) if missing else ""

    def _load_registry(self) -> dict:
        if not self.registry_path.is_file():
            return _registry_template()
        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except Exception:
            return _registry_template()
        if not isinstance(payload, dict):
            return _registry_template()
        payload.setdefault("schema_version", SCHEMA_VERSION)
        payload.setdefault("storage_provider", "bunny")
        payload.setdefault("updated_at", "")
        payload.setdefault("articles", {})
        payload.setdefault("objects", {})
        if not isinstance(payload["articles"], dict):
            payload["articles"] = {}
        if not isinstance(payload["objects"], dict):
            payload["objects"] = {}
        return payload

    def _write_registry(self) -> float:
        started = time.perf_counter()
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry["schema_version"] = SCHEMA_VERSION
        self.registry["storage_provider"] = "bunny"
        self.registry["updated_at"] = _utc_now()
        tmp = self.registry_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(self.registry_path)
        self.stats["registry_writes"] += 1
        elapsed = time.perf_counter() - started
        self.timing["registry_write_seconds"] += elapsed
        return elapsed

    def _repair_registry_source_names(self) -> int:
        """Backfill blank publisher labels from durable source article URLs."""
        started = time.perf_counter()
        repaired = 0
        for row in self.registry.get("articles", {}).values():
            if not isinstance(row, dict) or str(row.get("source_name") or "").strip():
                continue
            inferred = _infer_source_name(str(row.get("source_article_url") or ""))
            if inferred:
                row["source_name"] = inferred
                repaired += 1
        if repaired:
            self.stats["metadata_repairs"] += repaired
            self._write_registry()
        self.timing["metadata_repair_seconds"] += time.perf_counter() - started
        return repaired

    def _public_url(self, storage_key: str) -> str:
        return f"{self.public_base}/{storage_key.lstrip('/')}"

    def _storage_url(self, storage_key: str) -> str:
        zone = quote(self.zone, safe="")
        key = quote(storage_key.lstrip("/"), safe="/")
        return f"https://{self.storage_host}/{zone}/{key}"

    def _download(self, source_url: str):
        headers = {
            "User-Agent": "TreasureCoastToday/1.0 (+https://treasurecoast.today/)",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }
        with self.session.get(source_url, headers=headers, timeout=(7, 25), stream=True, allow_redirects=True) as response:
            response.raise_for_status()
            content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if content_type and not content_type.startswith("image/"):
                raise ValueError(f"source returned non-image content type {content_type}")
            announced = str(response.headers.get("Content-Length") or "").strip()
            if announced.isdigit() and int(announced) > self.max_bytes:
                raise ValueError(f"image exceeds {self.max_bytes} byte safety limit")
            chunks = []
            total = 0
            digest = hashlib.sha256()
            for chunk in response.iter_content(chunk_size=256 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > self.max_bytes:
                    raise ValueError(f"image exceeds {self.max_bytes} byte safety limit")
                digest.update(chunk)
                chunks.append(chunk)
            if not total:
                raise ValueError("source returned an empty image")
            final_url = str(getattr(response, "url", "") or source_url)
            return b"".join(chunks), digest.hexdigest(), content_type, final_url, {
                "etag": str(response.headers.get("ETag") or "").strip(),
                "last_modified": str(response.headers.get("Last-Modified") or "").strip(),
            }

    def _source_changed_since(self, source_url: str, current: dict) -> bool:
        """Use publisher validators to detect same-URL byte changes without a download."""
        etag = str(current.get("etag") or "").strip()
        last_modified = str(current.get("last_modified") or "").strip()
        if not etag and not last_modified:
            return False
        self.stats["source_revalidations"] += 1
        try:
            response = self.session.head(
                source_url,
                headers={"User-Agent": "TreasureCoastToday/1.0 (+https://treasurecoast.today/)"},
                timeout=(5, 10),
                allow_redirects=True,
            )
            if not (200 <= response.status_code < 300):
                return False
            remote_etag = str(response.headers.get("ETag") or "").strip()
            remote_last_modified = str(response.headers.get("Last-Modified") or "").strip()
            changed = False
            if etag and remote_etag:
                changed = etag != remote_etag
            elif last_modified and remote_last_modified:
                changed = last_modified != remote_last_modified
            if changed:
                self.stats["source_changes_detected"] += 1
            return changed
        except Exception:
            # A source HEAD failure must never break a known-good mirror.
            return False

    def _upload(self, storage_key: str, content: bytes, content_type: str) -> None:
        headers = {"AccessKey": self.password}
        if content_type:
            headers["Content-Type"] = content_type
        response = self.session.put(
            self._storage_url(storage_key),
            data=content,
            headers=headers,
            timeout=(7, 30),
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"Bunny upload returned HTTP {response.status_code}")

    def _verify_public(self, public_url: str, expected_bytes: int) -> None:
        last_error = None
        for delay in (0.0, 0.5, 1.5):
            if delay:
                time.sleep(delay)
            try:
                response = self.session.head(public_url, timeout=(5, 12), allow_redirects=True)
                if response.status_code == 405:
                    response = self.session.get(public_url, timeout=(5, 12), stream=True, allow_redirects=True)
                if 200 <= response.status_code < 300:
                    announced = str(response.headers.get("Content-Length") or "").strip()
                    if announced.isdigit() and int(announced) not in {0, expected_bytes}:
                        raise RuntimeError(
                            f"Bunny verification length mismatch ({announced} != {expected_bytes})"
                        )
                    return
                last_error = RuntimeError(f"Bunny public URL returned HTTP {response.status_code}")
            except Exception as exc:  # verification must fail closed to publisher URL
                last_error = exc
        raise last_error or RuntimeError("Bunny public URL verification failed")

    def _record_failure(self, *, slug: str, original_url: str, source_article_url: str, source_name: str, error: Exception) -> float:
        now = _utc_now()
        source_name = str(source_name or _infer_source_name(source_article_url)).strip()
        articles = self.registry.setdefault("articles", {})
        row = articles.setdefault(slug, {"canonical_slug": slug, "history": []})
        prior = row.get("current_image") if isinstance(row.get("current_image"), dict) else None
        if prior and prior.get("original_url") != original_url:
            hist = row.setdefault("history", [])
            old = dict(prior)
            old["replaced_at"] = now
            if old not in hist:
                hist.append(old)
        row.update({
            "canonical_slug": slug,
            "source_name": source_name or row.get("source_name", ""),
            "source_article_url": source_article_url or row.get("source_article_url", ""),
            "last_attempt_at": now,
        })
        row["current_image"] = {
            "original_url": original_url,
            "public_url": "",
            "storage_key": "",
            "sha256": "",
            "content_type": "",
            "byte_length": 0,
            "storage_provider": "bunny",
            "status": "external",
            "error": f"{type(error).__name__}: {error}"[:500],
            "first_seen": now,
            "mirrored_at": "",
        }
        return self._write_registry()

    def mirror(self, *, slug: str, original_url: str, source_article_url: str = "", source_name: str = "") -> dict:
        """Mirror one publisher image and return a delivery decision.

        The original URL is always returned on failure.  A mirrored URL is returned as
        ``resolved_url`` only in mirror mode and only after the provenance registry is
        atomically written.
        """
        original_url = str(original_url or "").strip()
        slug = str(slug or "").strip()
        source_article_url = str(source_article_url or "").strip()
        source_name = str(source_name or _infer_source_name(source_article_url)).strip()
        candidate_started = time.perf_counter()
        event_timing = {
            "download": 0.0,
            "upload": 0.0,
            "verify": 0.0,
            "revalidate": 0.0,
            "registry_write": 0.0,
            "total": 0.0,
        }
        result = {
            "mode": self.mode,
            "original_url": original_url,
            "resolved_url": original_url,
            "public_url": "",
            "storage_key": "",
            "sha256": "",
            "status": "external",
            "action": "external",
        }
        if not slug or not original_url.startswith(("http://", "https://")):
            return result
        self.stats["candidates"] += 1
        if self.mode == "external":
            return result
        if self.config_error:
            self.stats["fallbacks"] += 1
            result.update(status="external", action="configuration_fallback", error=self.config_error)
            event_timing["total"] = time.perf_counter() - candidate_started
            self.timing["candidate_seconds"] += event_timing["total"]
            return result

        articles = self.registry.setdefault("articles", {})
        article_row = articles.get(slug) if isinstance(articles.get(slug), dict) else {}
        current = article_row.get("current_image") if isinstance(article_row.get("current_image"), dict) else {}
        source_changed = False
        if (
            current.get("status") == "mirrored"
            and current.get("original_url") == original_url
            and current.get("public_url")
            and current.get("storage_key")
            and current.get("sha256")
        ):
            _revalidation_started = time.perf_counter()
            source_changed = self._source_changed_since(original_url, current)
            event_timing["revalidate"] = time.perf_counter() - _revalidation_started
            self.timing["revalidation_seconds"] += event_timing["revalidate"]
        if (
            current.get("status") == "mirrored"
            and current.get("original_url") == original_url
            and current.get("public_url")
            and current.get("storage_key")
            and current.get("sha256")
            and not source_changed
        ):
            self.stats["registry_hits"] += 1
            public_url = str(current["public_url"])
            result.update({
                "resolved_url": public_url if self.mode == "mirror" else original_url,
                "public_url": public_url,
                "storage_key": str(current["storage_key"]),
                "sha256": str(current["sha256"]),
                "status": "mirrored",
                "action": "registry_hit",
            })
            event_timing["total"] = time.perf_counter() - candidate_started
            self.timing["candidate_seconds"] += event_timing["total"]
            self.events.append({
                "slug": slug,
                "action": "registry_hit",
                "original_url": original_url,
                "public_url": public_url,
                "timing_seconds": {k: round(v, 3) for k, v in event_timing.items()},
            })
            return result

        try:
            _download_started = time.perf_counter()
            try:
                content, sha256, content_type, final_source_url, validators = self._download(original_url)
            finally:
                event_timing["download"] = time.perf_counter() - _download_started
                self.timing["download_seconds"] += event_timing["download"]
            self.stats["downloads"] += 1
            extension = _extension_for(content_type, final_source_url or original_url)
            object_row = self.registry.setdefault("objects", {}).get(sha256)
            if isinstance(object_row, dict) and object_row.get("public_url") and object_row.get("storage_key"):
                storage_key = str(object_row["storage_key"])
                public_url = str(object_row["public_url"])
                self.stats["hash_dedupe_hits"] += 1
                action = "hash_dedupe_hit"
            else:
                storage_key = f"articles/{sha256[:2]}/{sha256}{extension}"
                public_url = self._public_url(storage_key)
                _upload_started = time.perf_counter()
                try:
                    self._upload(storage_key, content, content_type)
                finally:
                    event_timing["upload"] = time.perf_counter() - _upload_started
                    self.timing["upload_seconds"] += event_timing["upload"]
                self.stats["uploads"] += 1
                _verify_started = time.perf_counter()
                try:
                    self._verify_public(public_url, len(content))
                finally:
                    event_timing["verify"] = time.perf_counter() - _verify_started
                    self.timing["verification_seconds"] += event_timing["verify"]
                self.stats["verified"] += 1
                self.registry.setdefault("objects", {})[sha256] = {
                    "storage_provider": "bunny",
                    "storage_key": storage_key,
                    "public_url": public_url,
                    "content_type": content_type,
                    "byte_length": len(content),
                    "created_at": _utc_now(),
                }
                action = "uploaded"

            now = _utc_now()
            row = articles.setdefault(slug, {"canonical_slug": slug, "history": []})
            prior = row.get("current_image") if isinstance(row.get("current_image"), dict) else None
            if prior and (
                prior.get("original_url") != original_url
                or prior.get("sha256") != sha256
                or prior.get("public_url") != public_url
            ):
                old = dict(prior)
                old["replaced_at"] = now
                hist = row.setdefault("history", [])
                if old not in hist:
                    hist.append(old)
            first_seen = (
                prior.get("first_seen")
                if prior and prior.get("original_url") == original_url and prior.get("first_seen")
                else now
            )
            row.update({
                "canonical_slug": slug,
                "source_name": source_name or row.get("source_name", ""),
                "source_article_url": source_article_url or row.get("source_article_url", ""),
                "last_attempt_at": now,
            })
            row["current_image"] = {
                "original_url": original_url,
                "final_source_url": final_source_url or original_url,
                "public_url": public_url,
                "storage_key": storage_key,
                "sha256": sha256,
                "content_type": content_type,
                "byte_length": len(content),
                "etag": validators.get("etag", ""),
                "last_modified": validators.get("last_modified", ""),
                "storage_provider": "bunny",
                "status": "mirrored",
                "error": "",
                "first_seen": first_seen,
                "mirrored_at": now,
            }
            # Critical ordering: provenance is durable before a mirrored URL can be
            # returned to the page renderer.
            event_timing["registry_write"] = self._write_registry()
            result.update({
                "resolved_url": public_url if self.mode == "mirror" else original_url,
                "public_url": public_url,
                "storage_key": storage_key,
                "sha256": sha256,
                "status": "mirrored",
                "action": action,
            })
            event_timing["total"] = time.perf_counter() - candidate_started
            self.timing["candidate_seconds"] += event_timing["total"]
            self.events.append({
                "slug": slug,
                "action": action,
                "original_url": original_url,
                "public_url": public_url,
                "timing_seconds": {k: round(v, 3) for k, v in event_timing.items()},
            })
            return result
        except Exception as exc:
            self.stats["fallbacks"] += 1
            try:
                event_timing["registry_write"] = self._record_failure(
                    slug=slug,
                    original_url=original_url,
                    source_article_url=source_article_url,
                    source_name=source_name,
                    error=exc,
                )
            except Exception:
                pass
            result.update(status="external", action="mirror_failed", error=f"{type(exc).__name__}: {exc}"[:500])
            event_timing["total"] = time.perf_counter() - candidate_started
            self.timing["candidate_seconds"] += event_timing["total"]
            self.events.append({
                "slug": slug,
                "action": "mirror_failed",
                "original_url": original_url,
                "error": result["error"],
                "timing_seconds": {k: round(v, 3) for k, v in event_timing.items()},
            })
            return result

    def write_report(self) -> dict:
        image_work_elapsed = self.timing["candidate_seconds"] + self.timing["metadata_repair_seconds"]
        report = {
            "schema_version": 1,
            "generated_at": _utc_now(),
            "mode": self.mode,
            "configured": not bool(self.config_error),
            "configuration_error": self.config_error,
            "storage_provider": "bunny",
            "storage_zone": self.zone,
            "storage_host": self.storage_host,
            "public_base_url": self.public_base,
            # Keep elapsed_seconds for compatibility, but make it honest: it now
            # measures cumulative image-stage work instead of manager lifetime.
            "elapsed_seconds": round(image_work_elapsed, 3),
            "image_work_elapsed_seconds": round(image_work_elapsed, 3),
            "manager_lifetime_seconds": round(time.perf_counter() - self.started, 3),
            "timing_seconds": {k: round(v, 3) for k, v in self.timing.items()},
            "summary": dict(self.stats),
            "events": self.events[-200:],
        }
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return report


_INSTANCE = None
_INSTANCE_ROOT = None


def get_article_image_mirror(root: Path) -> ArticleImageMirror:
    global _INSTANCE, _INSTANCE_ROOT
    resolved = Path(root).resolve()
    if _INSTANCE is None or _INSTANCE_ROOT != resolved:
        _INSTANCE = ArticleImageMirror(resolved)
        _INSTANCE_ROOT = resolved
    return _INSTANCE


def reset_article_image_mirror_for_tests() -> None:
    global _INSTANCE, _INSTANCE_ROOT
    _INSTANCE = None
    _INSTANCE_ROOT = None


def finalize_article_image_mirror(root: Path):
    """Write a shadow/mirror report even when a run produced zero candidates."""
    if _INSTANCE is None:
        if _normalized_mode() not in {"shadow", "mirror"}:
            return None
        get_article_image_mirror(root)
    if _INSTANCE_ROOT != Path(root).resolve():
        return None
    return _INSTANCE.write_report()
