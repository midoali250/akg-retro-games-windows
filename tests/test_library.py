import unittest
from library import load_catalog, filter_catalog
class CatalogTests(unittest.TestCase):
 def test_catalog_and_exclusions(self):
  x=load_catalog('drive-index.json');self.assertEqual(len(x),97);self.assertEqual(sum(g['system']=='SNES' for g in x),1)
  self.assertFalse(any(g['id']=='1Rg1ArsidLLlZGnFXJPgY8ba8flRI-M-r' for g in x))
 def test_filter_and_search(self):
  x=load_catalog('drive-index.json');self.assertEqual(len(filter_catalog(x,'SNES')),1)
  self.assertTrue(all('mario' in g['title'].lower() for g in filter_catalog(x,query='MARIO')))
  self.assertEqual(filter_catalog(x,'FAVORITES',favorites={x[0]['id']}),[x[0]])
if __name__=='__main__':unittest.main()
