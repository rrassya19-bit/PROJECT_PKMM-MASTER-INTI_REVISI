"""Persistent, deduplicated notification engine for the BARA prototype.

Detection and delivery are deliberately separate: a notification is stored
before any delivery attempt, and a failed delivery never deletes it.

Persistence intentionally follows the existing prototype pattern
(``monitor_state.json``): one JSON document, a process-wide lock, and atomic
``.tmp`` replacement. This keeps the implementation compatible with the active
Flask prototype without introducing a database dependency.
"""
import json
import logging
import math
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc

SEVERITIES = ('INFO', 'WASPADA', 'DARURAT')
SOURCES = ('FIRMS', 'SENTINEL2', 'XGBOOST', 'SYSTEM')
NOTIFICATION_STATUSES = ('UNREAD', 'READ', 'ACKNOWLEDGED', 'RESOLVED', 'DISMISSED')
EVENT_STATUSES = ('OPEN', 'MONITORING', 'VERIFIED', 'RESOLVED', 'DISMISSED')
CHANNELS = ('IN_APP', 'EMAIL', 'PUSH', 'TELEGRAM')
DELIVERY_STATUSES = ('PENDING', 'SENT', 'FAILED', 'RETRYING')
FIRMS_QUALIFYING_CONFIDENCE = ('h', 'n')

SEVERITY_RANK = {'INFO': 0, 'WASPADA': 1, 'DARURAT': 2}
OPEN_EVENT_STATUSES = ('OPEN', 'MONITORING')

MAX_EVIDENCE_PER_EVENT = 50


def now_iso():
    return datetime.now(UTC).isoformat()


def _new_id(prefix):
    return prefix + uuid.uuid4().hex


def _coerce_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def valid_coordinates(lat, lon):
    """Return True only for finite coordinates inside valid WGS84 ranges."""
    return (lat is not None and lon is not None
            and -90 <= lat <= 90 and -180 <= lon <= 180)


def coordinate_cell(value):
    """Round a coordinate to a ~1 km identity cell without '-0.0'."""
    rounded = round(float(value), 2)
    if rounded == 0:
        rounded = 0.0
    return f'{rounded:.2f}'


def parse_firms_time(point):
    try:
        return datetime.strptime(
            str(point['date']) + str(point['time']).zfill(4), '%Y-%m-%d%H%M'
        ).replace(tzinfo=UTC)
    except (KeyError, TypeError, ValueError):
        return None


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None


def _safe_text(value, limit=500):
    text = str(value if value is not None else '').strip()
    return text[:limit]


class NotificationEngine:
    def __init__(self, path, min_score=0.5, max_notifications=2000,
                 max_events=1000, firm_window_hours=24, scene_window_days=14,
                 logger=None):
        self.path = Path(path)
        self.lock = threading.RLock()
        self.min_score = float(min_score)
        # 0 means "retain without limit" for the corresponding collection.
        self.max_notifications = max(0, int(max_notifications))
        self.max_events = max(0, int(max_events))
        self.firm_window_hours = max(1, int(firm_window_hours))
        self.scene_window_days = max(1, int(scene_window_days))
        self.log = logger or logging.getLogger(__name__)
        self.data = self._load()

    # ------------------------------------------------------------------ store
    def _empty(self):
        return {
            'version': 1,
            'events': [],
            'notifications': [],
            'deliveries': [],
            'meta': {'updated_at': None},
        }

    def _load(self):
        if not self.path.exists():
            return self._empty()
        try:
            loaded = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            backup = self.path.with_suffix(self.path.suffix + '.corrupt')
            try:
                self.path.replace(backup)
            except OSError:
                pass
            self.log.warning('Notification state was unreadable (%s); starting a fresh store at %s.', type(exc).__name__, backup)
            return self._empty()
        if not isinstance(loaded, dict):
            return self._empty()
        base = self._empty()
        for key in ('events', 'notifications', 'deliveries'):
            value = loaded.get(key)
            base[key] = value if isinstance(value, list) else []
        meta = loaded.get('meta')
        if isinstance(meta, dict):
            base['meta'] = meta
        return base

    def _save(self):
        self.data['meta']['updated_at'] = now_iso()
        temporary = self.path.with_suffix(self.path.suffix + '.tmp')
        temporary.write_text(
            json.dumps(self.data, ensure_ascii=False, allow_nan=False),
            encoding='utf-8'
        )
        temporary.replace(self.path)

    def _prune(self):
        notifications = self.data['notifications']
        if self.max_notifications and len(notifications) > self.max_notifications:
            notifications.sort(key=lambda item: item.get('created_at') or '')
            self.data['notifications'] = notifications[-self.max_notifications:]

        events = self.data['events']
        if self.max_events and len(events) > self.max_events:
            protected = [e for e in events if e.get('status') in OPEN_EVENT_STATUSES]
            removable = [e for e in events if e.get('status') not in OPEN_EVENT_STATUSES]
            removable.sort(key=lambda item: item.get('last_detected_at') or '')
            keep = max(0, self.max_events - len(protected))
            self.data['events'] = protected + removable[-keep:] if keep else protected

    # --------------------------------------------------------------- lookup
    def _find_event(self, event_key):
        for event in self.data['events']:
            if event.get('event_key') == event_key:
                return event
        return None

    def _find_notification(self, notification_id):
        for notification in self.data['notifications']:
            if notification.get('id') == notification_id:
                return notification
        return None

    def _event_summary(self, event_id):
        for event in self.data['events']:
            if event.get('id') == event_id:
                return event.get('status'), event.get('severity')
        return None, None

    def _decorate(self, notification):
        status, severity = self._event_summary(notification.get('event_id'))
        row = dict(notification)
        row['event_status'] = status
        row['event_severity'] = severity
        return row

    # ---------------------------------------------------------- event logic
    def _upsert_event(self, *, source, event_key, severity, latitude, longitude,
                      occurred_at, fingerprint, title, message):
        """Create or update an event. Returns a notification when warranted.

        A repeat of the same fingerprint (same FIRMS acquisition row, same
        Sentinel-2 scene) never creates another notification. Additional
        evidence updates the existing event; it only creates a new
        notification when severity escalates or a closed event reopens.
        """
        if source not in SOURCES:
            raise ValueError('Sumber notifikasi tidak dikenal.')
        if severity not in SEVERITIES:
            raise ValueError('Tingkat notifikasi tidak dikenal.')
        if severity == 'DARURAT':
            # Automatic paths must never manufacture an emergency declaration.
            raise ValueError('DARURAT hanya dapat dibuat melalui verifikasi petugas.')
        lat = _coerce_float(latitude)
        lon = _coerce_float(longitude)
        if lat is not None and lon is not None and not valid_coordinates(lat, lon):
            lat, lon = None, None

        event = self._find_event(event_key)
        should_notify = False
        if event is None:
            event = {
                'id': _new_id('evt_'),
                'event_key': event_key,
                'source': source,
                'severity': severity,
                'latitude': lat,
                'longitude': lon,
                'first_detected_at': occurred_at,
                'last_detected_at': occurred_at,
                'status': 'OPEN',
                'verified_by': None,
                'verified_at': None,
                'resolved_by': None,
                'resolved_at': None,
                'resolution_note': None,
                'evidence': [{'fingerprint': fingerprint, 'observed_at': occurred_at}],
            }
            self.data['events'].append(event)
            should_notify = True
        else:
            fingerprints = {item.get('fingerprint') for item in event.get('evidence', [])}
            if fingerprint in fingerprints:
                return None
            event.setdefault('evidence', []).append({
                'fingerprint': fingerprint,
                'observed_at': occurred_at,
            })
            if len(event['evidence']) > MAX_EVIDENCE_PER_EVENT:
                event['evidence'] = event['evidence'][-MAX_EVIDENCE_PER_EVENT:]
            if not event.get('first_detected_at') or occurred_at < event['first_detected_at']:
                event['first_detected_at'] = occurred_at
            if not event.get('last_detected_at') or occurred_at > event['last_detected_at']:
                event['last_detected_at'] = occurred_at
            if event.get('latitude') is None and lat is not None:
                event['latitude'], event['longitude'] = lat, lon
            previous = event.get('severity', 'INFO')
            if SEVERITY_RANK.get(severity, 0) > SEVERITY_RANK.get(previous, 0):
                event['severity'] = severity
                should_notify = True
            elif event.get('status') in ('RESOLVED', 'DISMISSED'):
                event['status'] = 'OPEN'
                event['verified_by'] = None
                event['verified_at'] = None
                event['resolved_by'] = None
                event['resolved_at'] = None
                event['resolution_note'] = None
                should_notify = True
            self._save()

        if not should_notify:
            return None
        return self._create_notification(
            event=event, severity=severity, source=source, title=title,
            message=message, occurred_at=occurred_at,
        )

    def _create_notification(self, *, event, severity, source, title, message,
                             occurred_at):
        notification = {
            'id': _new_id('ntf_'),
            'event_id': event['id'],
            'title': _safe_text(title, 160),
            'message': _safe_text(message, 1200),
            'severity': severity,
            'source': source,
            'latitude': event.get('latitude'),
            'longitude': event.get('longitude'),
            'occurred_at': occurred_at or now_iso(),
            'created_at': now_iso(),
            'read_at': None,
            'status': 'UNREAD',
        }
        self.data['notifications'].append(notification)
        self._prune()
        self._save()
        try:
            self.deliver(notification)
        except Exception as exc:  # delivery must never lose the stored record
            self.log.warning('Notification delivery failed: %s', type(exc).__name__)
            self._record_delivery(
                notification['id'], 'IN_APP', 'dashboard', 'FAILED',
                _safe_text(exc, 300),
            )
        return self._decorate(notification)

    def deliver(self, notification):
        """Default MVP delivery: in-app only. External channels plug in here."""
        self._record_delivery(notification['id'], 'IN_APP', 'dashboard', 'SENT', None)
        return {'channel': 'IN_APP', 'delivery_status': 'SENT'}

    def _record_delivery(self, notification_id, channel, recipient, status, error,
                         save=True):
        if channel not in CHANNELS:
            raise ValueError('Kanal pengiriman tidak dikenal.')
        if status not in DELIVERY_STATUSES:
            raise ValueError('Status pengiriman tidak dikenal.')
        record = {
            'id': _new_id('dlv_'),
            'notification_id': notification_id,
            'channel': channel,
            'recipient': _safe_text(recipient, 200),
            'delivery_status': status,
            'attempted_at': now_iso(),
            'error_message': _safe_text(error, 300) if error else None,
        }
        self.data['deliveries'].append(record)
        if save:
            self._save()
        return record

    def record_delivery(self, notification_id, channel='IN_APP',
                        recipient='dashboard', status='SENT', error=None):
        with self.lock:
            if self._find_notification(notification_id) is None:
                raise KeyError('Notifikasi tidak ditemukan.')
            return self._record_delivery(notification_id, channel, recipient, status, error)

    # ---------------------------------------------------------- entry points
    def evaluate_firms(self, points, now=None):
        """Evaluate raw FIRMS rows (as returned by ``fetch_hotspots``)."""
        if not isinstance(points, list):
            return 0
        now = now or datetime.now(UTC)
        created = 0
        with self.lock:
            for point in points:
                if not isinstance(point, dict):
                    continue
                lat = _coerce_float(point.get('lat'))
                lon = _coerce_float(point.get('lon'))
                if not valid_coordinates(lat, lon):
                    continue
                confidence = str(point.get('confidence') or '').lower()
                if confidence not in FIRMS_QUALIFYING_CONFIDENCE:
                    continue
                acquired = parse_firms_time(point)
                if acquired is None:
                    continue
                age = now - acquired
                if age < timedelta(minutes=-5) or age > timedelta(hours=self.firm_window_hours):
                    continue
                satellite = _safe_text(point.get('satellite') or 'unknown', 20)
                date = acquired.date().isoformat()
                event_key = 'firms:{}:{}:{}:{}'.format(
                    satellite, coordinate_cell(lat), coordinate_cell(lon), date
                )
                fingerprint = 'firms:{}:{}:{}:{}:{}'.format(
                    satellite, date, str(point.get('time') or '').zfill(4),
                    coordinate_cell(lat), coordinate_cell(lon)
                )
                frp = _coerce_float(point.get('frp')) or 0.0
                title = 'Anomali termal terdeteksi (FIRMS)'
                message = (
                    'Deteksi VIIRS {sat} pada {lat}, {lon} pukul {time} UTC; '
                    'keyakinan {conf}, FRP {frp:.1f} MW. Ini anomali panas '
                    'satelit, bukan konfirmasi kebakaran; verifikasi lapangan '
                    'diperlukan.'
                ).format(
                    sat=satellite, lat=f'{lat:.4f}', lon=f'{lon:.4f}',
                    time=acquired.strftime('%H:%M'), conf=confidence,
                    frp=frp,
                )
                if self._upsert_event(
                    source='FIRMS', event_key=event_key, severity='WASPADA',
                    latitude=lat, longitude=lon,
                    occurred_at=acquired.isoformat(), fingerprint=fingerprint,
                    title=title, message=message,
                ):
                    created += 1
        return created

    def evaluate_monitor_point(self, point, now=None):
        """Evaluate one grid point after the monitor worker updates it."""
        if not isinstance(point, dict):
            return 0
        now = now or datetime.now(UTC)
        lat = _coerce_float(point.get('lat'))
        lon = _coerce_float(point.get('lon'))
        if not valid_coordinates(lat, lon):
            return 0
        status = point.get('status')
        with self.lock:
            if status == 'error':
                message = _safe_text(point.get('error') or 'Pemrosesan citra belum berhasil.', 300)
                return 1 if self._record_info(
                    event_key='system:data:{}:{}:{}'.format(
                        coordinate_cell(lat), coordinate_cell(lon),
                        now.date().isoformat()
                    ),
                    fingerprint='data-error:{}'.format(now.date().isoformat()),
                    title='Analisis citra belum berhasil',
                    message=(
                        'Titik {}, {}: {}. Status ini bukan berarti wilayah aman; '
                        'data satelit belum dapat dinilai pada siklus tersebut.'
                    ).format(f'{lat:.4f}', f'{lon:.4f}', message),
                    latitude=lat, longitude=lon, occurred_at=now.isoformat(),
                ) else 0

            result = point.get('result')
            if status != 'ok' or not isinstance(result, dict):
                return 0
            if str(result.get('label')) != '1':
                return 0
            scene = result.get('scene') if isinstance(result.get('scene'), dict) else {}
            acquired = parse_iso(scene.get('datetime'))
            if acquired is None:
                return 0
            age = now - acquired
            if age < timedelta(days=-1) or age > timedelta(days=self.scene_window_days):
                return 0
            classes = [str(value) for value in result.get('classes') or []]
            probabilities = result.get('probabilities') or []
            score = None
            if '1' in classes and len(probabilities) == len(classes):
                try:
                    score = float(probabilities[classes.index('1')])
                except (TypeError, ValueError):
                    score = None
            if score is not None and score < self.min_score:
                return 0
            scene_id = _safe_text(scene.get('id') or 'unknown-scene', 120)
            event_key = 'xgboost:{}:{}:{}'.format(
                coordinate_cell(lat), coordinate_cell(lon),
                acquired.date().isoformat()
            )
            score_text = 'tidak tersedia' if score is None else f'{score * 100:.1f}%'
            created = self._upsert_event(
                source='XGBOOST', event_key=event_key, severity='WASPADA',
                latitude=lat, longitude=lon,
                occurred_at=acquired.isoformat(),
                fingerprint='scene:' + scene_id,
                title='Indikasi potensi terbakar (XGBoost)',
                message=(
                    'Kelas 1 pada titik {}, {} dengan skor {score}; citra {when}. '
                    'Ini indikasi potensi risiko, bukan konfirmasi kebakaran aktif.'
                ).format(
                    f'{lat:.4f}', f'{lon:.4f}', score=score_text,
                    when=acquired.strftime('%Y-%m-%d %H:%M UTC'),
                ),
            )
            return 1 if created else 0

    def evaluate_cycle(self, state, now=None):
        """Record one INFO notification per completed monitoring cycle."""
        if not isinstance(state, dict):
            return 0
        last_run = state.get('last_run')
        if not last_run:
            return 0
        points = state.get('points') or []
        ok = sum(1 for point in points if point.get('status') == 'ok')
        failed = sum(1 for point in points if point.get('status') == 'error')
        pending = sum(1 for point in points if point.get('status') in ('pending', 'running'))
        return 1 if self._record_info(
            event_key='system:cycle:' + str(last_run),
            fingerprint=str(last_run),
            title='Siklus pemantauan selesai',
            message=(
                'Siklus grid selesai: {} berhasil, {} gagal, {} menunggu. '
                'Kegagalan pemrosesan bukan bukti wilayah aman.'
            ).format(ok, failed, pending),
            occurred_at=str(last_run),
        ) else 0

    def evaluate_firms_unavailable(self, error=None, now=None):
        now = now or datetime.now(UTC)
        if isinstance(error, ValueError):
            detail = _safe_text(error, 300)
        else:
            detail = 'Layanan FIRMS tidak dapat dihubungi atau kuota API habis.'
        return 1 if self._record_info(
            event_key='system:firms:' + now.date().isoformat(),
            fingerprint='firms-unavailable:' + now.date().isoformat(),
            title='Data FIRMS belum dapat diperbarui',
            message=(
                '{}. Deteksi terbaru mungkin belum lengkap; kondisi ini bukan '
                'berarti tidak ada kebakaran.'
            ).format(detail),
            occurred_at=now.isoformat(),
        ) else 0

    def record_system_info(self, event_key, title, message, occurred_at=None):
        return self._record_info(
            event_key=event_key, fingerprint=event_key, title=title,
            message=message, occurred_at=occurred_at or now_iso(),
        )

    def _record_info(self, *, event_key, fingerprint, title, message,
                     latitude=None, longitude=None, occurred_at=None):
        notification = self._upsert_event(
            source='SYSTEM', event_key=event_key, severity='INFO',
            latitude=latitude, longitude=longitude,
            occurred_at=occurred_at or now_iso(), fingerprint=fingerprint,
            title=title, message=message,
        )
        return bool(notification)

    # ------------------------------------------------------------- read APIs
    def list_notifications(self, severity=None, status=None, read=None,
                           limit=50, offset=0):
        if severity and severity not in SEVERITIES:
            raise ValueError('Filter severity tidak dikenal.')
        if status and status not in NOTIFICATION_STATUSES:
            raise ValueError('Filter status tidak dikenal.')
        limit = max(1, min(200, int(limit)))
        offset = max(0, int(offset))
        with self.lock:
            rows = list(self.data['notifications'])
            rows.sort(key=lambda item: item.get('created_at') or '', reverse=True)
            unread_count = sum(1 for item in rows if item.get('status') == 'UNREAD')
            if severity:
                rows = [item for item in rows if item.get('severity') == severity]
            if status:
                rows = [item for item in rows if item.get('status') == status]
            if read is not None:
                if read:
                    rows = [item for item in rows if item.get('read_at')]
                else:
                    rows = [item for item in rows if not item.get('read_at')]
            total = len(rows)
            page = [self._decorate(item) for item in rows[offset:offset + limit]]
            return {
                'notifications': page,
                'total': total,
                'unread_count': unread_count,
                'limit': limit,
                'offset': offset,
            }

    def summary(self):
        with self.lock:
            counts = {severity: {'unread': 0, 'total': 0} for severity in SEVERITIES}
            for notification in self.data['notifications']:
                bucket = counts.get(notification.get('severity'))
                if bucket is None:
                    continue
                bucket['total'] += 1
                if notification.get('status') == 'UNREAD':
                    bucket['unread'] += 1
            return {
                'counts': counts,
                'unread_count': sum(item['unread'] for item in counts.values()),
                'total': sum(item['total'] for item in counts.values()),
            }

    def get_notification(self, notification_id):
        with self.lock:
            notification = self._find_notification(notification_id)
            if notification is None:
                raise KeyError('Notifikasi tidak ditemukan.')
            row = self._decorate(notification)
            event = None
            for candidate in self.data['events']:
                if candidate.get('id') == notification.get('event_id'):
                    event = dict(candidate)
                    break
            row['event'] = event
            row['deliveries'] = [
                dict(item) for item in self.data['deliveries']
                if item.get('notification_id') == notification_id
            ]
            return row

    def mark_read(self, notification_id):
        with self.lock:
            notification = self._find_notification(notification_id)
            if notification is None:
                raise KeyError('Notifikasi tidak ditemukan.')
            if notification.get('status') == 'UNREAD':
                notification['status'] = 'READ'
                notification['read_at'] = now_iso()
                self._save()
            return self._decorate(notification)

    def mark_all_read(self):
        with self.lock:
            changed = 0
            stamp = now_iso()
            for notification in self.data['notifications']:
                if notification.get('status') == 'UNREAD':
                    notification['status'] = 'READ'
                    notification['read_at'] = stamp
                    changed += 1
            if changed:
                self._save()
            return changed

    def set_status(self, notification_id, status):
        if status not in NOTIFICATION_STATUSES:
            raise ValueError('Status notifikasi tidak dikenal.')
        with self.lock:
            notification = self._find_notification(notification_id)
            if notification is None:
                raise KeyError('Notifikasi tidak ditemukan.')
            notification['status'] = status
            if status in ('READ', 'ACKNOWLEDGED', 'RESOLVED', 'DISMISSED'):
                notification['read_at'] = notification.get('read_at') or now_iso()
            else:
                notification['read_at'] = None
            self._save()
            return self._decorate(notification)

    def list_events(self, status=None, limit=100, offset=0):
        if status and status not in EVENT_STATUSES:
            raise ValueError('Filter status event tidak dikenal.')
        limit = max(1, min(500, int(limit)))
        offset = max(0, int(offset))
        with self.lock:
            rows = list(self.data['events'])
            rows.sort(key=lambda item: item.get('last_detected_at') or '', reverse=True)
            if status:
                rows = [item for item in rows if item.get('status') == status]
            total = len(rows)
            page = [dict(item) for item in rows[offset:offset + limit]]
            return {'events': page, 'total': total, 'limit': limit, 'offset': offset}

    def get_event(self, event_id):
        with self.lock:
            for event in self.data['events']:
                if event.get('id') == event_id:
                    row = dict(event)
                    row['notifications'] = [
                        self._decorate(item) for item in self.data['notifications']
                        if item.get('event_id') == event_id
                    ]
                    return row
        raise KeyError('Event tidak ditemukan.')

    def verify_event(self, event_id, verifier):
        """Escalate an event to DARURAT after authorized human verification."""
        verifier = _safe_text(verifier, 120)
        if len(verifier) < 2:
            raise ValueError('Nama petugas verifikator wajib diisi (minimal 2 karakter).')
        with self.lock:
            event = None
            for candidate in self.data['events']:
                if candidate.get('id') == event_id:
                    event = candidate
                    break
            if event is None:
                raise KeyError('Event tidak ditemukan.')
            if event.get('status') == 'VERIFIED':
                raise ValueError('Event ini sudah diverifikasi.')
            if event.get('status') == 'RESOLVED':
                raise ValueError('Event yang sudah diselesaikan tidak dapat diverifikasi.')
            stamp = now_iso()
            event['status'] = 'VERIFIED'
            event['verified_by'] = verifier
            event['verified_at'] = stamp
            event['severity'] = 'DARURAT'
            notification = self._create_notification(
                event=event,
                severity='DARURAT',
                source=event.get('source') if event.get('source') in SOURCES else 'SYSTEM',
                title='DARURAT — telah diverifikasi petugas',
                message=(
                    'Event {} diverifikasi oleh {}. Tingkat DARURAT hanya '
                    'ditetapkan setelah verifikasi petugas; tetap bukan '
                    'pernyataan darurat resmi tanpa otoritas berwenang.'
                ).format(event.get('event_key'), verifier),
                occurred_at=stamp,
            )
            self._save()
            return {'event': dict(event), 'notification': notification}

    def resolve_event(self, event_id, actor, note=None):
        """Close an event after review. Notification read state is untouched."""
        actor = _safe_text(actor, 120)
        if len(actor) < 2:
            raise ValueError('Nama petugas penyelesai wajib diisi (minimal 2 karakter).')
        note = _safe_text(note, 500) if note else None
        with self.lock:
            event = None
            for candidate in self.data['events']:
                if candidate.get('id') == event_id:
                    event = candidate
                    break
            if event is None:
                raise KeyError('Event tidak ditemukan.')
            if event.get('status') == 'RESOLVED':
                raise ValueError('Event ini sudah diselesaikan.')
            stamp = now_iso()
            event['status'] = 'RESOLVED'
            event['resolved_by'] = actor
            event['resolved_at'] = stamp
            event['resolution_note'] = note
            self._save()
            row = dict(event)
            row['notifications'] = [
                self._decorate(item) for item in self.data['notifications']
                if item.get('event_id') == event_id
            ]
            return {'event': row}


class NotificationWorker:
    """Bounded background FIRMS polling so alerts do not depend on the UI."""

    def __init__(self, engine, fetch_firms, interval_seconds=900, logger=None):
        self.engine = engine
        self.fetch_firms = fetch_firms
        self.interval_seconds = max(60, int(interval_seconds))
        self.log = logger or logging.getLogger(__name__)
        self.stop_event = threading.Event()
        self.thread = None

    def run_once(self):
        try:
            result = self.fetch_firms() or {}
            self.engine.evaluate_firms(result.get('points') or [])
        except Exception as exc:
            self.log.warning('FIRMS notification poll failed: %s', type(exc).__name__)
            try:
                self.engine.evaluate_firms_unavailable(exc)
            except Exception:
                self.log.exception('Could not record FIRMS unavailability')

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._run, name='notification-firms', daemon=True
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _run(self):
        while not self.stop_event.wait(self.interval_seconds):
            self.run_once()
