import asyncio
import unittest
from datetime import date
from unittest.mock import AsyncMock, patch
import main

class NutritionTests(unittest.TestCase):
    def test_all_curated_recipes_have_nutrient_values(self):
        self.assertEqual(main.APP_CURATED_MEAL_IDS, set(main.MEAL_RECIPES))
        for mid in main.APP_CURATED_MEAL_IDS:
            n = main.ingredient_nutrients(main.MEAL_RECIPES[mid]['ingredients'])
            self.assertGreater(n['kcal'], 0, mid)
            self.assertGreaterEqual(n['fiber'], 0, mid)

    def test_personal_energy_estimate_and_loss_deficit(self):
        profile={'age':'35','sex':'Женский','height':'165','weight':'65','activity':'Сидячая работа','goal':'Снизить вес'}
        result=main.nutrition_targets(profile)
        self.assertEqual(result['maintenance_kcal'],1614)
        self.assertEqual(result['kcal'],1372)
        self.assertGreater(result['protein'],0)
        self.assertGreater(result['carbs'],0)

    def test_no_calorie_target_when_required_measurements_missing(self):
        self.assertIsNone(main.nutrition_targets({'age':'35','height':'165','weight':'пропустить'}))
        self.assertIsNone(main.nutrition_targets({'age':'16','height':'165','weight':'55'}))

    def test_low_bmi_goal_does_not_create_weight_loss_deficit(self):
        profile={'age':'30','sex':'Женский','height':'170','weight':'49','activity':'Сидячая работа','goal':'Снизить вес'}
        result=main.nutrition_targets(profile)
        self.assertEqual(result['kcal'],result['maintenance_kcal'])
        self.assertIn('специалист',result['note'])

    def test_menu_portions_and_macros_are_recomputed_for_profile(self):
        profile={'age':'35','sex':'Женский','height':'165','weight':'65','activity':'Сидячая работа','goal':'Снизить вес'}
        targets=main.nutrition_targets(profile)
        plan=main.fallback_app_week_plan(123,date(2026,10,5),allowed_ids=main.APP_CURATED_MEAL_IDS,targets=targets)
        catalog=main.catalog_for_week({'plan_json':plan},profile)
        self.assertTrue(main.valid_app_week_plan(plan))
        self.assertEqual([len({d[i] for d in plan}) for i in range(4)],[7,7,7,7])
        for day in plan:
            totals={k:sum(catalog[mid][k] for mid in day) for k in ('kcal','protein','fat','carbs')}
            self.assertLess(abs(totals['kcal']-targets['kcal'])/targets['kcal'],0.15)
        self.assertTrue(all(meal['fiber']>=0 for meal in catalog.values()))

    def test_ai_menu_cannot_reintroduce_excluded_dairy(self):
        profile={'age':'35','sex':'Женский','height':'165','weight':'65','activity':'Сидячая работа','goal':'Поддерживать форму','food':'без молочных продуктов'}
        plan=[['proteinCurdEgg','proteinChickenBuckwheat','proteinEggCurdSnack','proteinChickenVeg'] for _ in range(7)]
        answer=__import__('json').dumps({'days':plan})
        with patch.object(main,'client',object()), patch.object(main,'get_profile',AsyncMock(return_value=profile)), patch.object(main,'ask_ai',AsyncMock(return_value=answer)) as ask:
            result=asyncio.run(main.generate_ai_app_week_plan(1,date(2026,10,5),allowed_ids=main.allowed_meal_ids(profile)))
        self.assertIsNone(result)
        prompt=ask.await_args.args[2]
        self.assertNotIn('proteinCurdEgg |',prompt)

if __name__=='__main__':
    unittest.main()
