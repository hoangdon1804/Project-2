import unittest
from unittest.mock import Mock, patch

from shapely.geometry import shape
import external_services as service


def relation(identifier, name, level="6", rings=None):
    rings = rings or [("outer", [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)])]
    return {"type": "relation", "id": identifier,
            "tags": {"name": name, "boundary": "administrative", "admin_level": level},
            "members": [{"type": "way", "ref": i, "role": role,
                         "geometry": [{"lon": x, "lat": y} for x, y in coords]}
                        for i, (role, coords) in enumerate(rings)]}


class WardImportTests(unittest.TestCase):
    def setUp(self):
        service._CACHE.clear()
        city_check = patch.object(service, "_in_city", return_value=True)
        city_check.start()
        self.addCleanup(city_check.stop)

    def test_city_aliases(self):
        for name in ("Hà Nội", "Thành phố Hà Nội", "TP. Hà Nội"):
            self.assertEqual(service._city_code(name), "VN-HN")
        for name in ("TP HCM", "TP.HCM", "Thành phố Hồ Chí Minh", "Sài Gòn"):
            self.assertEqual(service._city_code(name), "VN-SG")

    def test_exact_normalized_names(self):
        self.assertTrue(service._matches(relation(1, "Phường Cầu Giấy"), "cau giay"))
        self.assertFalse(service._matches(relation(1, "Quận 10"), "Quận 1"))
        self.assertFalse(service._matches(relation(1, "Xã A"), "Phường A"))

    def test_holes_and_multipolygon_remain_one_ward(self):
        rel = relation(1, "Phường A", rings=[
            ("outer", [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)]),
            ("inner", [(1, 1), (2, 1), (2, 2), (1, 2), (1, 1)]),
            ("outer", [(6, 0), (7, 0), (7, 1), (6, 1), (6, 0)]),
        ])
        wards = service.osm_to_geojson({"elements": [rel, rel]})
        self.assertEqual(len(wards), 1)
        self.assertEqual(wards[0]["geometry"]["type"], "MultiPolygon")
        self.assertEqual(shape(wards[0]["geometry"]).area, 16)

    def test_incomplete_boundary_is_not_silently_imported(self):
        rel = relation(1, "Phường A", rings=[("outer", [(0, 0), (1, 0), (1, 1)])])
        with self.assertRaises(service.WardImportError):
            service.osm_to_geojson({"elements": [rel]})

    @patch.object(service.requests, "post")
    def test_partial_http_200_response_uses_backup(self, post):
        post.side_effect = [Mock(json=Mock(return_value={"remark": "runtime timeout", "elements": []})),
                            Mock(json=Mock(return_value={"elements": [relation(1, "Phường A")]}))]
        self.assertEqual(len(service._query("query")["elements"]), 1)
        self.assertEqual(post.call_count, 2)

    @patch.object(service.requests, "post")
    def test_failures_are_not_cached(self, post):
        post.side_effect = service.requests.Timeout()
        with self.assertRaises(service.WardImportError):
            service._catalog("VN-HN")
        self.assertFalse(service._CACHE)

    @patch.object(service, "_query")
    def test_catalog_scopes_by_city_and_caches_success(self, query):
        city = relation(100, "Hà Nội", "4")
        city["tags"]["ISO3166-2"] = "VN-HN"
        query.return_value = {"elements": [city, relation(1, "Phường A")]}
        result = service._catalog("VN-HN")
        self.assertEqual([e["id"] for e in result["elements"]], [1])
        self.assertIn('"VN-HN"', query.call_args.args[0])
        self.assertIn("city_geometry", result)
        self.assertEqual(service._catalog("VN-HN"), result)
        query.assert_called_once()

    @patch.object(service, "_catalog")
    def test_unknown_place_does_not_fall_back_to_unscoped_search(self, catalog):
        catalog.return_value = {"elements": []}
        with self.assertRaises(service.WardImportError):
            service.fetch_wards_from_osm('Unknown "place"', "Hà Nội")
        self.assertEqual(catalog.call_count, 2)

    def test_city_border_neighbor_is_excluded(self):
        # Exercise the real city check despite other tests' catalog fixture stub.
        patch.stopall()
        outside = relation(2, "Phường B", rings=[
            ("outer", [(4, 0), (5, 0), (5, 4), (4, 4), (4, 0)])])
        city = service.osm_to_geojson({"elements": [relation(1, "Hà Nội")]})[0]["geometry"]
        self.assertFalse(service._in_city(outside, {"city_geometry": city}))

    @patch.object(service, "_catalog")
    def test_current_ward_is_returned_directly(self, catalog):
        catalog.return_value = {"elements": [relation(7, "Phường Cầu Giấy")]}
        result = service.fetch_wards_from_osm("cau giay", "Hà Nội")
        self.assertEqual(result["elements"][0]["id"], 7)
        self.assertIsNone(result["snapshot"])
        catalog.assert_called_once_with("VN-HN")

    @patch.object(service, "_catalog")
    def test_old_district_excludes_neighbor_touching_border(self, catalog):
        catalog.return_value = {"elements": [relation(1, "Quận 1"),
            relation(2, "Phường A", "8"),
            relation(3, "Phường B", "8", [("outer", [(4, 0), (5, 0), (5, 4), (4, 4), (4, 0)])])]}
        result = service.fetch_wards_from_osm("Quan 1", "TP HCM")
        self.assertEqual([e["id"] for e in result["elements"]], [2])
        self.assertEqual(result["snapshot"], service.HISTORICAL_DATE)
        catalog.assert_called_once_with("VN-SG", historical=True)

    @patch.object(service, "_catalog")
    def test_ambiguous_name_is_rejected(self, catalog):
        catalog.return_value = {"elements": [relation(1, "Phường A"), relation(2, "Xã A")]}
        with self.assertRaises(service.WardImportError):
            service.fetch_wards_from_osm("A", "Hà Nội")


if __name__ == "__main__":
    unittest.main()
