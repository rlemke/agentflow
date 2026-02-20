scripts/teardown --all
scripts/rebuild
scripts/setup  --clean --build --hdfs --mirror /Volumes/afl_data/osm --runners 3 --osm-agents 4 --agents 1
scripts/seed-examples --clean
#scripts/run-workflow
./examples/osm-geocoder/tests/real/scripts/run_30states.sh
