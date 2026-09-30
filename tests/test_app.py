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
    def test_restrictions_do_not_get_generic_workout(self):
        plan=main.workout_plan_for_profile({"restrictions":"боль в колене"})
        self.assertEqual(plan["exercises"],[])
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
