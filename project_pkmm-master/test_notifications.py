"""Tests for the persistent notification engine and its Flask API contract."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from notifications import NotificationEngine, NotificationWorker, UTC
import server


def firms_point(now=None, **overrides):
    now = now or datetime.now(UTC)
    point = dict(
        lat=-2.2, lon=113.9, confidence='h', frp=12.5,
        date=now.strftime('%Y-%m-%d'), time=now.strftime('%H%M'),
        satellite='N', daynight='D',
    )
    point.update(overrides)
    return point


def monitor_point(now=None, label='1', score=0.8, status='ok', error=None,
                  scene_age_days=1):
    now = now or datetime.now(UTC)
    scene_time = now - timedelta(days=scene_age_days)
    return dict(
        id='1-1', lat=-2.2, lon=113.9, status=status,
        error=error, checked_at=now.isoformat(),
        result=None if status != 'ok' else dict(
            label=label, classes=['0', '1'], probabilities=[1 - score, score],
            scene=dict(id='scene-' + scene_time.strftime('%Y%m%d'), datetime=scene_time.isoformat()),
            warning='test',
        ),
    )


class NotificationEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'notification_state.json'
        self.engine = NotificationEngine(self.path, min_score=0.5)
        self.now = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)

    def tearDown(self):
        self.temp.cleanup()

    def test_repeated_polling_does_not_duplicate(self):
        point = firms_point(self.now)
        self.assertEqual(self.engine.evaluate_firms([point], self.now), 1)
        self.assertEqual(self.engine.evaluate_firms([point], self.now), 0)
        self.assertEqual(self.engine.evaluate_firms([point], self.now), 0)
        data = self.engine.list_notifications()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['unread_count'], 1)
        events = self.engine.list_events()['events']
        self.assertEqual(len(events), 1)
        self.assertEqual(len(events[0]['evidence']), 1)

    def test_new_supporting_evidence_updates_event(self):
        self.engine.evaluate_firms([firms_point(self.now)], self.now)
        later = firms_point(self.now, time='1230')
        later_now = self.now + timedelta(minutes=30)
        self.assertEqual(self.engine.evaluate_firms([later], later_now), 0)
        events = self.engine.list_events()['events']
        self.assertEqual(len(events), 1)
        self.assertEqual(len(events[0]['evidence']), 2)
        self.assertEqual(events[0]['last_detected_at'], (self.now + timedelta(minutes=30)).isoformat())
        self.assertEqual(self.engine.list_notifications()['total'], 1)

    def test_low_confidence_and_invalid_coordinates_are_ignored(self):
        self.assertEqual(self.engine.evaluate_firms(
            [firms_point(self.now, confidence='l')], self.now), 0)
        self.assertEqual(self.engine.evaluate_firms(
            [firms_point(self.now, lat=999, lon=113.9)], self.now), 0)
        self.assertEqual(self.engine.evaluate_firms(
            [firms_point(self.now, lat=40, lon=-3)], self.now), 1)

    def test_xgboost_class_one_is_waspada_never_darurat(self):
        self.assertEqual(self.engine.evaluate_monitor_point(monitor_point(self.now), self.now), 1)
        rows = self.engine.list_notifications()['notifications']
        self.assertEqual(rows[0]['severity'], 'WASPADA')
        self.assertEqual(rows[0]['source'], 'XGBOOST')
        self.assertIn('bukan konfirmasi', rows[0]['message'])
        self.assertEqual(rows[0]['event_status'], 'OPEN')
        # Re-running the same scene must not duplicate.
        self.assertEqual(self.engine.evaluate_monitor_point(monitor_point(self.now), self.now), 0)
        self.assertFalse(any(n['severity'] == 'DARURAT' for n in self.engine.list_notifications()['notifications']))

    def test_non_alerting_predictions_and_stale_scenes_are_ignored(self):
        self.assertEqual(self.engine.evaluate_monitor_point(
            monitor_point(self.now, label='0'), self.now), 0)
        self.assertEqual(self.engine.evaluate_monitor_point(
            monitor_point(self.now, score=0.2), self.now), 0)
        self.assertEqual(self.engine.evaluate_monitor_point(
            monitor_point(self.now, scene_age_days=15), self.now), 0)
        self.assertEqual(self.engine.list_notifications()['total'], 0)

    def test_failed_analysis_is_info_not_safe(self):
        point = monitor_point(self.now, status='error', error='Piksel tertutup awan')
        self.assertEqual(self.engine.evaluate_monitor_point(point, self.now), 1)
        row = self.engine.list_notifications()['notifications'][0]
        self.assertEqual(row['severity'], 'INFO')
        self.assertIn('bukan berarti wilayah aman', row['message'])
        self.assertEqual(self.engine.evaluate_monitor_point(point, self.now), 0)
        different = monitor_point(self.now, status='error', error='Layanan citra timeout')
        self.assertEqual(self.engine.evaluate_monitor_point(different, self.now), 0)

    def test_event_resolution_records_actor_and_note(self):
        self.engine.evaluate_firms([firms_point(self.now)], self.now)
        event = self.engine.list_events()['events'][0]
        result = self.engine.resolve_event(event['id'], 'Petugas Lapangan', 'Api padam')
        self.assertEqual(result['event']['status'], 'RESOLVED')
        self.assertEqual(result['event']['resolved_by'], 'Petugas Lapangan')
        self.assertEqual(result['event']['resolution_note'], 'Api padam')
        self.assertTrue(result['event']['resolved_at'])
        stored = self.engine.get_event(event['id'])
        self.assertEqual(stored['status'], 'RESOLVED')
        with self.assertRaises(ValueError):
            self.engine.resolve_event(event['id'], 'Petugas Lapangan')
        with self.assertRaises(ValueError):
            self.engine.resolve_event(event['id'], ' ')
        later = firms_point(self.now, time='1300')
        self.assertEqual(self.engine.evaluate_firms([later], self.now + timedelta(hours=1)), 1)
        reopened = self.engine.get_event(event['id'])
        self.assertEqual(reopened['status'], 'OPEN')
        self.assertIsNone(reopened['resolved_by'])

    def test_notification_accepts_resolved_status_and_unread_round_trip(self):
        self.engine.evaluate_firms([firms_point(self.now)], self.now)
        notification = self.engine.list_notifications()['notifications'][0]
        self.engine.set_status(notification['id'], 'RESOLVED')
        self.assertEqual(self.engine.list_notifications(status='RESOLVED')['total'], 1)
        self.engine.set_status(notification['id'], 'UNREAD')
        self.assertIsNone(self.engine.get_notification(notification['id'])['read_at'])
        self.assertEqual(self.engine.summary()['unread_count'], 1)

    def test_zero_retention_limit_keeps_full_history(self):
        engine = NotificationEngine(
            Path(self.temp.name) / 'unlimited.json',
            max_notifications=2, max_events=2,
        )
        for index in range(4):
            engine.record_system_info(f'key:{index}', 'Info', 'Pesan {}'.format(index))
            event_id = engine.list_events()['events'][0]['id']
            engine.resolve_event(event_id, 'Petugas A')
        self.assertEqual(len(engine.list_notifications()['notifications']), 2)
        self.assertEqual(len(engine.list_events()['events']), 2)
        engine.max_notifications = 0
        engine.max_events = 0
        for index in range(4, 6):
            engine.record_system_info(f'key:{index}', 'Info', 'Pesan {}'.format(index))
        self.assertEqual(len(engine.list_notifications()['notifications']), 4)
        self.assertEqual(len(engine.list_events()['events']), 4)

    def test_event_verification_creates_darurat(self):
        self.engine.evaluate_firms([firms_point(self.now)], self.now)
        event = self.engine.list_events()['events'][0]
        result = self.engine.verify_event(event['id'], 'Petugas Verifikasi')
        self.assertEqual(result['event']['status'], 'VERIFIED')
        self.assertEqual(result['event']['verified_by'], 'Petugas Verifikasi')
        self.assertEqual(result['notification']['severity'], 'DARURAT')
        self.assertEqual(result['notification']['source'], 'FIRMS')
        with self.assertRaises(ValueError):
            self.engine.verify_event(event['id'], 'Petugas Verifikasi')
        with self.assertRaises(ValueError):
            self.engine.verify_event(event['id'], ' ')

    def test_read_status_filtering_and_allowlists(self):
        self.engine.evaluate_firms([firms_point(self.now)], self.now)
        notification = self.engine.list_notifications()['notifications'][0]
        self.engine.mark_read(notification['id'])
        self.assertEqual(self.engine.list_notifications(read=False)['total'], 0)
        self.assertEqual(self.engine.list_notifications(status='READ')['total'], 1)
        self.engine.set_status(notification['id'], 'ACKNOWLEDGED')
        self.assertEqual(self.engine.list_notifications(status='ACKNOWLEDGED')['total'], 1)
        with self.assertRaises(ValueError):
            self.engine.set_status(notification['id'], 'HACKED')
        with self.assertRaises(ValueError):
            self.engine.list_notifications(severity='PANIC')
        with self.assertRaises(ValueError):
            self.engine.record_delivery(notification['id'], channel='FAX')

    def test_mark_all_read_counts_only_unread(self):
        self.engine.evaluate_firms([firms_point(self.now)], self.now)
        self.engine.evaluate_monitor_point(monitor_point(self.now), self.now)
        self.assertEqual(self.engine.mark_all_read(), 2)
        self.assertEqual(self.engine.mark_all_read(), 0)
        self.assertEqual(self.engine.summary()['unread_count'], 0)

    def test_delivery_failure_keeps_stored_notification(self):
        def broken_delivery(notification):
            raise RuntimeError('channel offline')
        self.engine.deliver = broken_delivery
        self.engine.evaluate_firms([firms_point(self.now)], self.now)
        rows = self.engine.list_notifications()['notifications']
        self.assertEqual(len(rows), 1)
        detail = self.engine.get_notification(rows[0]['id'])
        self.assertEqual(detail['deliveries'][-1]['delivery_status'], 'FAILED')
        self.assertEqual(detail['deliveries'][-1]['channel'], 'IN_APP')
        self.assertIn('channel offline', detail['deliveries'][-1]['error_message'])

    def test_persistence_across_restart(self):
        self.engine.evaluate_firms([firms_point(self.now)], self.now)
        notification = self.engine.list_notifications()['notifications'][0]
        self.engine.mark_read(notification['id'])
        reloaded = NotificationEngine(self.path)
        data = reloaded.list_notifications()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['notifications'][0]['status'], 'READ')
        self.assertEqual(len(reloaded.list_events()['events']), 1)
        self.assertEqual(len(reloaded.get_notification(notification['id'])['deliveries']), 1)

    def test_untrusted_text_is_stored_bounded_for_escaping(self):
        point = monitor_point(self.now, status='error', error='<script>alert(1)</script>' + 'x' * 2000)
        self.engine.evaluate_monitor_point(point, self.now)
        row = self.engine.list_notifications()['notifications'][0]
        self.assertLessEqual(len(row['message']), 1200)
        self.assertLessEqual(len(row['title']), 160)


class NotificationApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = NotificationEngine(Path(self.temp.name) / 'notifications.json')
        self.patch = patch.object(server, 'NOTIFIER', self.engine)
        self.patch.start()
        self.client = server.app.test_client()
        self.now = datetime.now(UTC)
        self.engine.evaluate_firms([firms_point(self.now)], self.now)
        self.notification = self.engine.list_notifications()['notifications'][0]

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_list_and_detail(self):
        response = self.client.get('/api/notifications')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['notifications'][0]['severity'], 'WASPADA')
        detail = self.client.get('/api/notifications/' + self.notification['id'])
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()['event']['source'], 'FIRMS')

    def test_read_acknowledge_and_summary(self):
        response = self.client.post('/api/notifications/' + self.notification['id'] + '/read')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['status'], 'READ')
        response = self.client.post(
            '/api/notifications/' + self.notification['id'] + '/status',
            json={'status': 'ACKNOWLEDGED'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['status'], 'ACKNOWLEDGED')
        response = self.client.post(
            '/api/notifications/' + self.notification['id'] + '/status',
            json={'status': 'RESOLVED'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['status'], 'RESOLVED')
        summary = self.client.get('/api/notifications/summary').get_json()
        self.assertEqual(summary['unread_count'], 0)
        self.assertEqual(self.client.post('/api/notifications/read-all').status_code, 200)

    def test_unknown_and_invalid_values(self):
        self.assertEqual(self.client.get('/api/notifications/missing-id').status_code, 404)
        self.assertEqual(self.client.post('/api/notifications/missing-id/read').status_code, 404)
        self.assertEqual(self.client.get('/api/notifications?severity=PANIC').status_code, 400)
        self.assertEqual(self.client.get('/api/notifications?read=maybe').status_code, 400)
        self.assertEqual(
            self.client.post('/api/notifications/' + self.notification['id'] + '/status',
                             json={'status': 'HACKED'}).status_code, 400)

    def test_verify_requires_token_when_configured(self):
        event = self.client.get('/api/events').get_json()['events'][0]
        with patch.dict(os.environ, {'VERIFY_TOKEN': 'secret'}):
            denied = self.client.post('/api/events/' + event['id'] + '/verify',
                                      json={'verifier': 'Petugas A'})
            self.assertEqual(denied.status_code, 403)
            allowed = self.client.post(
                '/api/events/' + event['id'] + '/verify',
                headers={'X-Verify-Token': 'secret'},
                json={'verifier': 'Petugas A'},
            )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.get_json()['notification']['severity'], 'DARURAT')
        self.assertEqual(self.client.post('/api/events/missing/verify', json={'verifier': 'A B'}).status_code, 404)

    def test_resolve_requires_token_and_records_actor(self):
        event = self.client.get('/api/events').get_json()['events'][0]
        with patch.dict(os.environ, {'VERIFY_TOKEN': 'secret'}):
            denied = self.client.post('/api/events/' + event['id'] + '/resolve',
                                      json={'actor': 'Petugas B', 'note': 'Padam'})
            self.assertEqual(denied.status_code, 403)
            allowed = self.client.post(
                '/api/events/' + event['id'] + '/resolve',
                headers={'X-Verify-Token': 'secret'},
                json={'actor': 'Petugas B', 'note': 'Padam'},
            )
        self.assertEqual(allowed.status_code, 200)
        body = allowed.get_json()['event']
        self.assertEqual(body['status'], 'RESOLVED')
        self.assertEqual(body['resolved_by'], 'Petugas B')
        self.assertEqual(body['resolution_note'], 'Padam')
        self.assertEqual(self.client.post('/api/events/missing/resolve',
                                          json={'actor': 'A B'}).status_code, 404)


class NotificationWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = NotificationEngine(Path(self.temp.name) / 'notifications.json')
        self.now = datetime.now(UTC)

    def tearDown(self):
        self.temp.cleanup()

    def test_worker_evaluates_firms_batches(self):
        worker = NotificationWorker(
            self.engine, lambda: {'points': [firms_point(self.now)]}, interval_seconds=60)
        worker.run_once()
        worker.run_once()
        self.assertEqual(self.engine.list_notifications()['total'], 1)

    def test_worker_records_firms_unavailability(self):
        def broken():
            raise ValueError('NASA FIRMS MAP_KEY belum diisi.')
        worker = NotificationWorker(self.engine, broken, interval_seconds=60)
        worker.run_once()
        row = self.engine.list_notifications()['notifications'][0]
        self.assertEqual(row['severity'], 'INFO')
        self.assertIn('bukan', row['message'])
        self.assertIn('berarti tidak ada kebakaran', row['message'])


if __name__ == '__main__':
    unittest.main()
