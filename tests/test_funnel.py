import unittest
from unittest.mock import AsyncMock, patch
from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update, Message
import main

class FunnelTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.old_storage = main.dp.fsm.storage
        main.dp.fsm.storage = MemoryStorage()
        self.bot = Bot('123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi')
        self.sent = []
        async def send(bot, method, **kwargs):
            self.sent.append(method)
            if method.__class__.__name__ in ('SendMessage','EditMessageText'):
                return Message.model_validate({'message_id':99,'date':1,'chat':{'id':123,'type':'private'},'text':getattr(method,'text','')},context={'bot':bot})
            return True
        self.bot.session = AsyncMock(side_effect=send)
        self.settings = dict(enabled=True, timezone='Europe/Moscow',morning_time='08:00',evening_time='20:00',workout_days='0,2,4')
        self.writes = AsyncMock()
        self.patches = [patch.object(main,'has_consent',AsyncMock(return_value=True)),patch.object(main,'get_profile',AsyncMock(return_value={'frequency':'3'})),patch.object(main,'ensure_ready',AsyncMock(return_value=True)),patch.object(main,'ensure_notification_settings',AsyncMock(side_effect=lambda uid:dict(self.settings))),patch.object(main,'db_execute',self.writes),patch.object(main,'ask_ai',AsyncMock(return_value='ИИ временно недоступен'))]
        for p in self.patches:p.start()
        self.seq=0
        self.state=main.dp.fsm.get_context(bot=self.bot,chat_id=123,user_id=123)

    async def asyncTearDown(self):
        for p in reversed(self.patches):p.stop()
        await main.dp.fsm.storage.close()
        main.dp.fsm.storage=self.old_storage

    async def message(self,text=None):
        self.seq+=1
        msg={'message_id':self.seq,'date':1,'chat':{'id':123,'type':'private'},'from':{'id':123,'is_bot':False,'first_name':'Test'}}
        if text is not None:msg['text']=text
        else:msg['photo']=[{'file_id':'test','file_unique_id':'test','width':10,'height':10}]
        await main.dp.feed_update(self.bot,Update.model_validate({'update_id':self.seq,'message':msg}))

    async def callback(self,value):
        self.seq+=1
        await main.dp.feed_update(self.bot,Update.model_validate({'update_id':self.seq,'callback_query':{'id':str(self.seq),'from':{'id':123,'is_bot':False,'first_name':'Test'},'chat_instance':'test','data':value,'message':{'message_id':99,'date':1,'chat':{'id':123,'type':'private'},'text':'Расписание'}}}))

    async def test_onboarding_choices_and_invalid_input(self):
        await self.state.set_state(main.Onboarding.age)
        await self.message('не число')
        self.assertEqual(await self.state.get_state(),'Onboarding:age')
        await self.message('35')
        self.assertEqual(await self.state.get_state(),'Onboarding:sex')
        self.assertIn('Женский',str(self.sent[-1].reply_markup))
        await self.message('Женский')
        await self.message('165')
        await self.message('65,5')
        await self.message('Снизить вес')
        await self.message('Сидячая работа')
        await self.message('0')
        self.assertEqual(await self.state.get_state(),'Onboarding:equipment')
        self.assertEqual((await self.state.get_data())['weight'],'65.5')
        self.assertEqual(main.workout_days_from_frequency('0'),'')

    async def test_photo_does_not_break_question(self):
        await self.state.set_state(main.Onboarding.name)
        await self.message()
        self.assertEqual(await self.state.get_state(),'Onboarding:name')
        self.assertIn('текстом',self.sent[-1].text)

    async def test_report_all_steps_saved_before_ai(self):
        await self.message('📊 Отчёт')
        self.assertIn('по одному пункту',self.sent[-1].text)
        for value in ['По плану','Выполнена','5000–10000 шагов','7,5','7','4','Хорошо','Не хватило времени']:
            await self.message(value)
        self.assertIsNone(await self.state.get_state())
        args=self.writes.call_args.args
        self.assertIn('INSERT INTO checkins',args[0])
        self.assertIn('Энергия: 7',args[2])
        self.assertIn('Сон: 7.5 ч',args[2])
        for label in ['Питание:', 'Тренировка:', 'Шаги/активность:', 'Сон:', 'Энергия:', 'Голод:', 'Самочувствие:', 'Что было сложным:']:
            self.assertIn(label,args[2])
        self.assertIn('Что было сложным: Не хватило времени',args[2])
        self.assertTrue(any(getattr(m,'text','')=='Отчёт сохранён ✅' for m in self.sent))

    async def test_report_validates_sleep_hours_without_advancing(self):
        await self.message('📊 Отчёт')
        await self.message('По плану')
        await self.message('Выполнена')
        await self.message('5000–10000 шагов')
        await self.message('28')
        self.assertEqual((await self.state.get_data())['report_step'],3)
        self.assertIn('от 0 до 24',self.sent[-1].text)

    async def test_menu_is_not_saved_as_report(self):
        await self.message('📊 Отчёт')
        await self.message('⏰ Расписание')
        self.assertIsNone(await self.state.get_state())
        self.writes.assert_not_awaited()
        self.assertIn('Автоматическое сопровождение',self.sent[-1].text)

    async def test_cancel_report(self):
        await self.message('📊 Отчёт')
        await self.message('✖️ Отмена')
        self.assertIsNone(await self.state.get_state())
        self.writes.assert_not_awaited()

    async def test_day_selection_and_custom_time(self):
        await self.callback('notify_day_2')
        self.assertEqual(self.writes.call_args.args[2],'0,4')
        await self.callback('notify_custom_m')
        await self.message('25:90')
        self.assertEqual(await self.state.get_state(),'ScheduleInput:time')
        await self.message('7:35')
        self.assertEqual(self.writes.call_args.args[2],'07:35')
        self.assertIsNone(await self.state.get_state())

    async def test_invalid_time_callback_does_not_write(self):
        await self.callback('notify_m_9999')
        self.writes.assert_not_awaited()

    async def test_callback_requires_profile(self):
        with patch.object(main,'get_profile',AsyncMock(return_value=None)):
            await self.callback('notify_day_2')
        self.writes.assert_not_awaited()

    async def test_complete_onboarding_saves_profile_and_shows_schedule(self):
        from datetime import date
        await self.state.set_state(main.Onboarding.name)
        with patch.object(main,'ensure_subscription',AsyncMock()), patch.object(main,'user_local_date',AsyncMock(return_value=date(2026,10,1))):
            for value in ['Тест','35','Женский','165','65','Снизить вес','Сидячая работа','3','Дома без оборудования','Нет','Без ограничений','7–8 часов']:
                await self.message(value)
        self.assertIsNone(await self.state.get_state())
        self.assertTrue(any('INSERT INTO profiles' in c.args[0] for c in self.writes.call_args_list))
        self.assertTrue(any('notify_day_0' in str(getattr(m,'reply_markup','')) for m in self.sent))

    async def test_same_schedule_value_is_safe(self):
        from aiogram.exceptions import TelegramBadRequest
        call=type('Call',(),{'message':type('Msg',(),{'edit_text':AsyncMock(side_effect=TelegramBadRequest(method=object(),message='Bad Request: message is not modified'))})()})()
        await main.edit_schedule(call,self.settings)
