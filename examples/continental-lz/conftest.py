"""Conftest for continental-lz example.

Excludes tests under the handlers/ symlink (which points to
osm-geocoder/handlers/) — those tests are collected from their
canonical location in examples/osm-geocoder/.
"""

collect_ignore_glob = ["handlers/**/test_*.py"]
