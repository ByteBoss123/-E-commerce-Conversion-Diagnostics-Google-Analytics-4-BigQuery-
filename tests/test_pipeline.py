import copy, unittest
from pipeline import validate,wilson,report,warnings
# Hand-constructed fixtures are tests only; never deployed as observations.
def sample():
 return {'schema_version':1,'classification':'historical_obfuscated_sample','start_date':'2020-11-01','end_date':'2020-11-01','generated_at':'2026-10-25T00:00:00Z','rows':[{'date':'2020-11-01','device':'mobile','acquisition_source':'test','sessions':100,'views':80,'carts':40,'checkouts':20,'purchases':10,'purchasing_sessions':12}], 'quality':{'raw_events':300,'observed_days':1,'excluded_identity_events':0,'purchase_events':12,'missing_transaction_events':0,'missing_revenue_events':0,'negative_revenue_events':0,'duplicate_transaction_events':0}}
class Tests(unittest.TestCase):
 def test_valid(self): self.assertEqual(validate(sample())['rows'][0]['sessions'],100)
 def test_nested(self):
  s=sample();s['rows'][0]['purchases']=21
  with self.assertRaises(ValueError):validate(s)
 def test_duplicate(self):
  s=sample();s['rows']*=2
  with self.assertRaises(ValueError):validate(s)
 def test_zero_interval(self): self.assertIsNone(wilson(0,0))
 def test_known_interval(self):
  lo,hi=wilson(50,100);self.assertAlmostEqual(lo,.40383,places=4);self.assertAlmostEqual(hi,.59617,places=4)
 def test_negative(self):
  s=sample();s['rows'][0]['views']=-1
  with self.assertRaises(ValueError):validate(s)
 def test_date(self):
  s=sample();s['rows'][0]['date']='2021-01-01'
  with self.assertRaises(ValueError):validate(s)
 def test_report(self):self.assertIn('12.50%',report(sample()))
 def test_purchase_bounds(self):
  s=sample();s['rows'][0]['purchasing_sessions']=101
  with self.assertRaises(ValueError):validate(s)
 def test_report_lists_all_quality_checks(self):
  r=report(sample())
  for f in ('excluded identity events','duplicate transaction events','missing revenue events','negative revenue events'):self.assertIn(f,r)
 def test_duplicate_check_not_evaluable(self):
  s=sample();s['quality']['missing_transaction_events']=12
  self.assertTrue(any('not evaluable' in w for w in warnings(s)))
  self.assertFalse(any('not evaluable' in w for w in warnings(sample())))
 def test_largest_loss_named(self):
  s=sample();s['rows'][0].update(views=80,carts=1,checkouts=1,purchases=0)
  self.assertIn('product view → add to cart (79 sessions)',report(s))
 def test_quality(self):
  s=sample();s['quality']['excluded_identity_events']=301
  with self.assertRaises(ValueError):validate(s)
if __name__=='__main__': unittest.main()
