import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

from aiogram.fsm.storage.base import StorageKey
import main


@unittest.skipUnless(os.getenv('TEST_DATABASE_URL'), 'Dedicated test database not configured')
class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.url_patch = patch.object(main, 'DATABASE_URL', os.environ['TEST_DATABASE_URL'])
        self.url_patch.start()
        await main.init_db()
        await main.db_execute('TRUNCATE telegram_inbox, bot_fsm, users, profiles, app_subscriptions, app_daily_state')

    async def asyncTearDown(self):
        await main.pool.close()
        main.pool = None
        self.url_patch.stop()

    async def test_schema_can_be_initialized_twice(self):
        await main.pool.close()
        await main.init_db()
        row = await main.db_fetchrow("SELECT to_regclass('idx_messages_user_time') AS name")
        self.assertEqual(row['name'], 'idx_messages_user_time')

    async def test_fsm_survives_new_storage_instance(self):
        key = StorageKey(bot_id=1, chat_id=123, user_id=123)
        first = main.PostgresStorage()
        await first.set_state(key, 'Onboarding:weight')
        await first.set_data(key, {'name': 'Тест'})
        second = main.PostgresStorage()
        self.assertEqual(await second.get_state(key), 'Onboarding:weight')
        self.assertEqual(await second.get_data(key), {'name': 'Тест'})

    async def test_overlapping_workers_only_process_once(self):
        await main.db_execute("INSERT INTO telegram_inbox(update_id,payload) VALUES(7,'{\"update_id\":7}')")
        async def consume(*args):
            await asyncio.sleep(0.1)
        consumer = AsyncMock(side_effect=consume)
        with patch.object(main.dp, 'feed_update', consumer):
            await asyncio.gather(main.process_next_inbox_update(), main.process_next_inbox_update())
        self.assertEqual(consumer.await_count, 1)
        row = await main.db_fetchrow('SELECT processed,payload FROM telegram_inbox WHERE update_id=7')
        self.assertTrue(row['processed'])
        self.assertEqual(json.loads(row['payload']), {})

    async def test_deletion_inside_worker_does_not_deadlock(self):
        await main.db_execute("INSERT INTO telegram_inbox(update_id,payload) VALUES(8,$1::jsonb)", json.dumps({'update_id':8, 'message':{'message_id':1,'date':1,'chat':{'id':123,'type':'private'},'from':{'id':123,'is_bot':False,'first_name':'Test'},'text':'/delete_me'}}))
        await main.db_execute("INSERT INTO app_daily_state(telegram_id,state_key,data) VALUES(123,'shopping:2026-10-01','{}')")
        async def delete(*args):
            await main.delete_user_data(123)
        with patch.object(main.dp, 'feed_update', AsyncMock(side_effect=delete)):
            await asyncio.wait_for(main.process_next_inbox_update(), 5)
        self.assertIsNone(await main.db_fetchrow('SELECT 1 FROM app_daily_state WHERE telegram_id=123'))
        self.assertIsNone(await main.db_fetchrow('SELECT 1 FROM telegram_inbox WHERE update_id=8'))
