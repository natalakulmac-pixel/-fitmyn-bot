import asyncio
import unittest
from datetime import date
from unittest.mock import AsyncMock, patch
import main

class PlanTests(unittest.TestCase):
    def test_week_schema_and_recipes(self):
        for mode in ("loss", "maintain", "gain"):
            plan = main.fallback_app_week_plan(123, date(2026,9,28), goal_mode=mode)
            self.assertTrue(main.valid_app_week_plan(plan))
            for day in plan:
                for mid in day:
                    meal = main.app_meal_payload(mid)
                    self.assertEqual(meal["id"],mid)
                    self.assertTrue(meal["recipe"])
                    self.assertTrue(all(isinstance(x,list) and len(x)==4 for x in meal["ingredients"]))
    def test_every_curated_meal_has_distinct_local_image(self):
        from pathlib import Path
        import hashlib
        images = [Path(main.__file__).parent / "assets" / "meals" / (mid + ".webp") for mid in main.APP_CURATED_MEAL_IDS]
        self.assertEqual(len(images), 28)
        hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in images}
        self.assertEqual(len(hashes), 28)

    def test_restrictions_do_not_get_generic_workout(self):
        plan=main.workout_plan_for_profile({"restrictions":"боль в колене"})
        self.assertEqual(plan["exercises"],[])
    def test_workout_catalog_covers_all_types_and_places(self):
        for kind in ("light", "cardio", "strength"):
            for place in ("home", "gym"):
                plan = main.workout_plan_for_profile({"restrictions":"нет"}, kind, place)
                self.assertTrue(plan["exercises"])
                self.assertEqual(plan["type"], kind)
                self.assertEqual(plan["location"], place)
                self.assertGreaterEqual(len(plan["exercises"]), 4)
                if kind == "light":
                    self.assertIn("усилие", plan["note"].lower())
    def test_restrictions_apply_to_every_workout_variant(self):
        for kind in ("light", "cardio", "strength"):
            for place in ("home", "gym"):
                self.assertEqual(main.workout_plan_for_profile({"restrictions":"беременность"}, kind, place)["exercises"], [])
    def test_dairy_exclusion(self):
        allowed=main.allowed_meal_ids({"food":"Без молочных продуктов"})
        self.assertNotIn("proteinCurdEgg",allowed)
        self.assertIn("eggBeans",allowed)
        plan=main.fallback_app_week_plan(123,date(2026,9,28),allowed_ids=allowed)
        self.assertTrue(all(mid in allowed for day in plan for mid in day))
    def test_goal_language(self):
        self.assertEqual(main.app_goal_mode({"goal":"Снизить массу тела"}),"loss")
        self.assertEqual(main.app_goal_mode({"goal":"Набрать вес"}),"gain")
    def test_no_auth(self):
        self.assertIsNone(main.validate_telegram_init_data(""))
    def test_app_routes(self):
        app=main.create_app()
        routes={str(r.resource) for r in app.router.routes()}
        self.assertTrue(any("/api/app/state" in r for r in routes))

class ProgressTests(unittest.IsolatedAsyncioTestCase):
    async def progress(self,start,current,target):
        rows=AsyncMock(side_effect=[{"weight":current},{"target_weight":target},{"weight":start}])
        with patch.object(main,"db_fetchrow",rows):
            return await main.get_app_goal_progress(1,{"weight":str(current)})
    async def test_gain_not_reached_at_start(self):
        p=await self.progress(60,60,70)
        self.assertEqual(p["progress_percent"],0)
        self.assertEqual(p["remaining_weight"],10)
    async def test_gain_halfway(self):
        p=await self.progress(60,65,70)
        self.assertEqual(p["progress_percent"],50)
    async def test_loss_halfway(self):
        p=await self.progress(70,65,60)
        self.assertEqual(p["progress_percent"],50)
    async def test_gain_crossed_target(self):
        p=await self.progress(60,72,70)
        self.assertEqual(p["progress_percent"],100)
        self.assertEqual(p["remaining_weight"],0)
    async def test_ai_outage_is_visible(self):
        fake=type("Client",(),{})()
        fake.responses=type("Responses",(),{})()
        fake.responses.create=AsyncMock(side_effect=RuntimeError("offline"))
        with patch.object(main,"client",fake),patch.object(main,"get_profile",AsyncMock(return_value=None)),patch.object(main,"recent_history",AsyncMock(return_value=[])),patch.object(main,"_ai_retry_after",0):
            result=await main.ask_ai(1,"Привет")
            self.assertIn("временно недоступен",result)

if __name__=="__main__":
    unittest.main()

class AccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_unexpected_handler_error_reaches_retry_worker(self):
        event=type("Event",(),{"exception":RuntimeError("temporary outage")})()
        with self.assertRaises(RuntimeError):
            await main.handle_expected_error(event)

    async def test_no_consent_never_starts_trial(self):
        request=type("Request",(),{"path":"/api/app/weight","headers":{}})()
        handler=AsyncMock()
        subscription=AsyncMock(return_value=True)
        with patch.object(main,"app_request_user",return_value={"id":123}),patch.object(main,"pool",object()),patch.object(main,"has_consent",AsyncMock(return_value=False)),patch.object(main,"subscription_has_access",subscription):
            response=await main.app_access_middleware(request,handler)
        self.assertEqual(response.status,403)
        subscription.assert_not_awaited()
        handler.assert_not_awaited()
    async def test_expired_write_blocked(self):
        request=type("Request",(),{"path":"/api/app/weight","headers":{}})()
        handler=AsyncMock()
        with patch.object(main,"app_request_user",return_value={"id":124}),patch.object(main,"pool",object()),patch.object(main,"has_consent",AsyncMock(return_value=True)),patch.object(main,"get_profile",AsyncMock(return_value={"name":"Test"})),patch.object(main,"subscription_has_access",AsyncMock(return_value=False)):
            response=await main.app_access_middleware(request,handler)
        self.assertEqual(response.status,402)
        handler.assert_not_awaited()
    async def test_cancel_failure_keeps_account(self):
        bot=AsyncMock()
        bot.edit_user_star_subscription.side_effect=RuntimeError("network")
        pool=object()
        with patch.object(main,"bot",bot),patch.object(main,"pool",pool),patch.object(main,"db_fetchrow",AsyncMock(return_value={"auto_renew":True,"telegram_payment_charge_id":"test"})):
            with self.assertRaises(RuntimeError):
                await main.delete_user_data(123)
